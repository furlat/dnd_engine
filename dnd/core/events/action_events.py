"""Serializable action-event facts and dependency-clean action specializations."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Self,
    Set,
    Tuple,
    TypeVar,
    cast,
    cast as type_cast,
)
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, StrictBool, StrictInt, model_validator

from dnd.core.action_execution import MovementTerminationReason
from dnd.core.combat_log import (
    ActionLogData,
    CombatLogEntry,
    CombatLogEntryType,
    MovementLogData,
    MultiEntityLogData,
    SpellInterruptionLogData,
    md_color,
)
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)
from dnd.core.behavior_context import active_behavior
from dnd.core.dice import DiceRoll
from dnd.core.elevation import support_distance_feet
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    _exact_event_evidence_equal,
)
from dnd.core.events.resolution_events import Damage
from dnd.core.events.item_events import ItemState
from dnd.core.events.world_events import MovementTrajectory
from dnd.core.traversal_connectors import (
    CONNECTOR_AUTHORED_ID_PATTERN,
    CONNECTOR_PRESENTATION_KEY_PATTERN,
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnectorKind,
)
from dnd.core.values import ModifiableValue
from dnd.presentation import ActionPresentationKind
from dnd.types.abilities import AbilityName
from dnd.types.actions import CostType
from dnd.types.damage import DamageType
from dnd.types.effects import EffectOrigin, EffectOriginKind
from dnd.types.behaviors import validate_behavior_id

COUNTERSPELL_INTERRUPTION_OUTCOME_CODE = "spell.counterspell.interrupted"
COUNTERSPELL_FAILURE_OUTCOME_CODE = "spell.counterspell.failed"

class BaseCost(BaseModel):
    """Serializable action cost without executable callbacks."""

    name: str = Field(default="A Cost", description="Human-readable cost label.")
    cost_type: CostType = Field(description="Action economy bucket consumed by this cost.")
    cost: int = Field(description="Amount consumed from the action economy bucket.")
    resource_name: Optional[str] = Field(
        default=None,
        description="Optional named resource consumed in addition to the action economy bucket.",
    )
    resource_cost: int = Field(default=0, description="Amount consumed from the named resource.")

class ActionEvent(Event):
    """Event emitted by the base action pipeline."""

    behavior_id: str = Field(
        default="action.unclassified",
        description="Direct semantic identity of the behavior producing this fact.",
    )
    provided_by_id: str = Field(
        default="action.unclassified",
        description="Direct semantic identity that installed the behavior.",
    )
    origin_root_id: Optional[str] = Field(
        default=None,
        description="Optional durable semantic root of the behavior.",
    )
    costs: List[BaseCost] = Field(default_factory=list, description="Serializable action costs.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="Usable item supplying this action when execution is item-bound.",
    )
    source_item_state: Optional[ItemState] = Field(
        default=None,
        description=(
            "Authoritative source-item state captured when the action was "
            "declared; replay never needs the live item registry."
        ),
    )
    item_charge_cost: int = Field(
        default=0,
        ge=0,
        description="Finite item charges consumed before this action completes.",
    )
    item_charge_action_lineage_uuid: Optional[UUID] = Field(
        default=None,
        description="Root action lineage authorized to consume the item resource once.",
    )
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DEFAULT,
        description="Stable presentation meaning for clients rendering this action.",
    )
    declared_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Complete entity target selection captured when the action is declared.",
    )
    application_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ordered target-application index for a convolution child event.",
    )
    application_id: Optional[UUID] = Field(
        default=None,
        description="Deterministic identity of one ordered target application.",
    )
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event type.")
    description: str = Field(default="", description="Action description for combat log generation")
    total_targets: int = Field(
        default=0,
        description="Number of targets affected by a multi-target or AoE action.",
    )
    total_damage: int = Field(
        default=0,
        description="Total damage dealt across all per-target child events.",
    )
    aoe_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Grid position targeted by a position-AoE action.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Freeze active direct identity before the event is registered."""
        active = active_behavior()
        if active is not None and self.behavior_id == "action.unclassified":
            self.behavior_id = active.behavior_id
        if self.provided_by_id == "action.unclassified":
            self.provided_by_id = (
                active.provided_by_id if active is not None else self.behavior_id
            )
        if self.origin_root_id is None and active is not None:
            self.origin_root_id = active.origin_root_id
        validate_behavior_id(self.behavior_id)
        validate_behavior_id(self.provided_by_id, "provided_by_id")
        if self.origin_root_id is not None:
            validate_behavior_id(self.origin_root_id, "origin_root_id")
        super().model_post_init(__context)

    def get_effect_origin(self) -> EffectOrigin:
        """Expose exact action provenance to persistent child effects."""
        return EffectOrigin(
            kind=EffectOriginKind.ACTION,
            source_id=self.behavior_id,
            source_event_lineage_uuid=str(self.lineage_uuid),
        )

    @classmethod
    def from_costs(
        cls,
        costs: List[BaseCost],
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
        source_item_uuid: Optional[UUID] = None,
        source_item_state: Optional[ItemState] = None,
        item_charge_cost: int = 0,
        declared_target_entity_uuids: Optional[List[UUID]] = None,
        presentation_kind: ActionPresentationKind = ActionPresentationKind.DEFAULT,
        behavior_id: str = "action.unclassified",
        provided_by_id: str = "action.unclassified",
        origin_root_id: Optional[str] = None,
    ) -> "ActionEvent":
        """Create an action event from runtime costs.

        Args:
            costs: Runtime costs to serialize on the event.
            source_entity_uuid: Acting entity UUID.
            target_entity_uuid: Optional primary target UUID.
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether the event should be registered immediately.
            source_item_uuid: Optional usable item supplying this action.
            source_item_state: Declaration-time authoritative item state.
            item_charge_cost: Finite item charges consumed on completion.
            declared_target_entity_uuids: Complete entity target selection.
            presentation_kind: Stable presentation meaning for this action.

        Returns:
            Newly created action event.
        """
        base_costs = [BaseCost.model_validate(cost) for cost in costs]
        event = cls(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target_entity_uuid,
            costs=base_costs,
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_item_uuid=source_item_uuid,
            source_item_state=source_item_state,
            item_charge_cost=item_charge_cost,
            declared_target_entity_uuids=declared_target_entity_uuids or [],
            behavior_id=behavior_id,
            provided_by_id=provided_by_id,
            origin_root_id=origin_root_id,
            presentation_kind=presentation_kind,
        )
        event.item_charge_action_lineage_uuid = event.lineage_uuid
        return event

    @model_validator(mode="after")
    def validate_item_state_facts(self) -> "ActionEvent":
        """Keep item and target-application identities internally coherent."""
        if self.source_item_state is not None:
            if self.source_item_uuid is None:
                raise ValueError("source item state requires source_item_uuid")
            if self.source_item_state.item_uuid != self.source_item_uuid:
                raise ValueError("source item state UUID must match source_item_uuid")
        if (
            self.presentation_kind is ActionPresentationKind.DRINK
            and self.source_item_state is None
        ):
            raise ValueError("drink action requires declaration-time item state")
        if (self.application_index is None) != (self.application_id is None):
            raise ValueError("application_index and application_id must be set together")
        return self

    def get_participant_entity_uuids(self) -> Set[UUID]:
        """Return the actor and every entity selected by the action.

        Returns:
            Direct event participants plus the declaration-time target set.
        """
        return super().get_participant_entity_uuids() | set(
            self.declared_target_entity_uuids
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return positions that spatial handlers should inspect for this event."""
        positions: Set[Tuple[int, int]] = set()
        if self.aoe_position:
            positions.add(self.aoe_position)
        return positions

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for generic actions.

        Uses self.name and self.description. Subclasses (AttackEvent,
        MovementEvent, SpellEvent) override with specific implementations.

        For multi-target actions (total_targets > 0), generates a summary log.
        Sub-entries come from _collect_child_combat_logs() via parent_event relationship.

        Returns:
            CombatLogEntry for self-targeting actions, or None for base events.
        """
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        source_name = self.source_entity_name or "Unknown"
        action_name = self.name or "Action"
        effect_desc = self.description or ""

        compact = f"{{cyan:{source_name}}} uses {{bold:{action_name}}}"
        verbose = compact + (f"\n  {effect_desc}" if effect_desc else "")
        detailed = verbose

        target_name = self.target_entity_name
        target_uuid = str(self.target_entity_uuid) if self.target_entity_uuid else None
        data = ActionLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            action_name=action_name,
            effect_description=effect_desc,
            target_name=target_name,
            target_uuid=target_uuid,
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=target_uuid,
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data.model_dump(),
            success=True
        )

    def _generate_multi_target_log(self) -> CombatLogEntry:
        """Generate summary log for multi-target actions.

        Per-target details are child event logs collected into sub-entries by
        the completion phase.

        Returns:
            Multi-entity combat-log summary.
        """
        source_name = self.source_entity_name or "Unknown"
        n_targets = self.total_targets
        total_dmg = self.total_damage or 0

        action_name = self.name or 'Action'
        if self.aoe_position:
            location = f" at ({self.aoe_position[0]}, {self.aoe_position[1]})"
        else:
            location = ""
        summary = f"{md_color(source_name, 'cyan')} uses {md_color(action_name, 'yellow')}{location} → {n_targets} targets, {md_color(str(total_dmg), 'red')} total damage"

        data = MultiEntityLogData(
            action_name=self.name or "Action",
            caster_name=source_name,
            total_targets=n_targets,
            total_damage=total_dmg,
            aoe_center=self.aoe_position
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            compact=summary,
            verbose=summary,
            detailed=summary,
            data=data.model_dump(),
            success=n_targets > 0
        )

ActionEventT = TypeVar("ActionEventT", bound=ActionEvent)

def _copy_observer_map(
    observer_map: Mapping[str, Set[str]],
) -> Dict[str, Set[str]]:
    """Detach one event-time observer map from a handler proposal."""
    return {
        key: set(observer_uuids)
        for key, observer_uuids in observer_map.items()
    }

class TraverseConnectorEvent(ActionEvent):
    """Immutable root transaction for one oriented connector transfer."""

    name: str = Field(default="Traverse Connector")
    event_type: EventType = Field(default=EventType.MOVEMENT)
    connector_uuid: UUID
    connector_authored_id: str = Field(
        pattern=CONNECTOR_AUTHORED_ID_PATTERN
    )
    connector_kind: TraversalConnectorKind
    connector_presentation_key: str = Field(
        pattern=CONNECTOR_PRESENTATION_KEY_PATTERN
    )
    connector_revision: StrictInt = Field(ge=1)
    connector_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    connector_provocation_policy: ConnectorProvocationPolicy
    connector_bidirectional: StrictBool
    start_position: Tuple[StrictInt, StrictInt]
    requested_end_position: Tuple[StrictInt, StrictInt]
    end_position: Tuple[StrictInt, StrictInt]
    objective_end_position: Optional[Tuple[StrictInt, StrictInt]] = None
    start_elevation_feet: StrictInt
    requested_end_elevation_feet: StrictInt
    end_elevation_feet: StrictInt
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: Optional[ConnectorActionCostType] = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    termination_reason: MovementTerminationReason = (
        MovementTerminationReason.COMPLETED
    )

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Detach connector proposals from queue-owned mutable containers."""
        del deep
        return super().model_copy(update=update, deep=True)

    def validate_handler_result(self, result: Event) -> Event:
        """Allow only an exact veto or queue-metadata-only result."""
        active_proposal = EventQueue.is_active_handler_proposal(result)
        queue_updates: Dict[str, object] = {
            "children_events": list(self.children_events),
            "lineage_children_events": list(self.lineage_children_events),
            "children_lineages": list(self.children_lineages),
            "identified_entity_observer_uuids": _copy_observer_map(
                self.identified_entity_observer_uuids
            ),
            "located_entity_observer_uuids": _copy_observer_map(
                self.located_entity_observer_uuids
            ),
            "located_position_observer_uuids": _copy_observer_map(
                self.located_position_observer_uuids
            ),
        }
        safe_status = (
            result.status_message
            if result.status_message is None or type(result.status_message) is str
            else self.status_message
        )

        def cancellation(status_message: str) -> TraverseConnectorEvent:
            canceled = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(TraverseConnectorEvent, canceled.model_copy(update={
                **queue_updates,
                "end_position": self.start_position,
                "objective_end_position": self.start_position,
                "end_elevation_feet": self.start_elevation_feet,
                "termination_reason": MovementTerminationReason.CANCELED,
                "outcome_code": "movement.canceled",
                "use_register": False if active_proposal else self.use_register,
            }))

        if type(result) is not TraverseConnectorEvent:
            return cancellation(
                "Connector traversal handler returned an incompatible event type"
            )
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and type(result.use_register) is bool
            and (result.status_message is None or type(result.status_message) is str)
        ):
            return cancellation(
                "Connector traversal handler returned malformed queue evidence"
            )
        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(update={"use_register": True})
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return cancellation(
                "Connector traversal handler changed lifecycle evidence"
            )
        if result.canceled:
            return cancellation(safe_status or "Connector traversal canceled")

        allowed_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
            "use_register",
        }
        if any(
            not _exact_event_evidence_equal(
                getattr(self, field_name),
                getattr(result, field_name),
            )
            for field_name in type(self).model_fields
            if field_name not in allowed_fields
        ):
            return cancellation(
                "Connector traversal handler changed immutable causal evidence"
            )
        if (
            not active_proposal
            and result.uuid == self.uuid
            and result.timestamp == self.timestamp
            and result.modified == self.modified
            and safe_status == self.status_message
        ):
            return self
        result_uuid = result.uuid
        changed = (
            result.timestamp != self.timestamp
            or safe_status != self.status_message
        )
        if result_uuid == self.uuid and changed:
            result_uuid = uuid4()
        return self.model_copy(update={
            **queue_updates,
            "uuid": result_uuid,
            "timestamp": result.timestamp,
            "modified": result.modified or changed,
            "status_message": safe_status,
            "use_register": False if active_proposal else self.use_register,
        })

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate objective connector settlement truth from frozen facts."""
        source_name = self.source_entity_name or "Unknown"
        committed = self.end_position != self.start_position
        distance_feet = (
            support_distance_feet(
                self.start_position,
                self.start_elevation_feet,
                self.end_position,
                self.end_elevation_feet,
            )
            if committed
            else 0
        )
        movement_cost = self.movement_cost_feet if committed else 0
        compact = (
            f"{md_color(source_name, 'cyan')} traverses a connector to "
            f"{md_color(str(self.end_position), 'yellow')}"
            if committed
            else f"{md_color(source_name, 'cyan')} cannot traverse the connector"
        )
        verbose = (
            f"{compact} ({self.start_position} → {self.end_position}, "
            f"{distance_feet}ft geometry, {movement_cost}ft movement)"
        )
        data = MovementLogData(
            movement_type="connector",
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            start_position=self.start_position,
            end_position=self.end_position,
            path=[self.start_position, self.end_position] if committed else [self.start_position],
            distance_feet=distance_feet,
            movement_cost=movement_cost,
            start_elevation_feet=self.start_elevation_feet,
            requested_end_elevation_feet=self.requested_end_elevation_feet,
            end_elevation_feet=self.end_elevation_feet,
            requested_end_position=self.requested_end_position,
            objective_end_position=self.objective_end_position,
            termination_reason=self.termination_reason.value,
            connector_uuid=str(self.connector_uuid),
            connector_authored_id=self.connector_authored_id,
            connector_kind=self.connector_kind.value,
            connector_presentation_key=self.connector_presentation_key,
            connector_revision=self.connector_revision,
            connector_digest=self.connector_digest,
            connector_provocation_policy=self.connector_provocation_policy.value,
            connector_action_cost_type=(
                self.action_cost_type.value
                if self.action_cost_type is not None
                else None
            ),
            connector_action_cost_amount=self.action_cost_amount,
            connector_bidirectional=self.connector_bidirectional,
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=data.model_dump(),
            success=(
                self.termination_reason is MovementTerminationReason.COMPLETED
                and committed
            ),
        )

class JumpEvent(ActionEvent):
    """Event payload for a jump movement."""

    name: str = Field(default="Jump", description="Human-readable jump event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized jump costs.")
    start_position: Tuple[int, int] = Field(description="Position occupied before the jump starts.")
    requested_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Accepted landing requested before settlement.",
    )
    end_position: Tuple[int, int] = Field(description="Voluntary landing actually committed, or takeoff.")
    objective_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Actor position after synchronous landing children.",
    )
    start_elevation_feet: int = Field(
        default=0,
        description="Support elevation at takeoff.",
    )
    requested_end_elevation_feet: int = Field(
        default=0,
        description="Accepted support elevation at the requested landing.",
    )
    end_elevation_feet: int = Field(
        default=0,
        description="Support elevation of the committed voluntary endpoint.",
    )
    jump_distance: int = Field(
        default=0,
        description="Accepted support-to-support movement cost in feet.",
    )
    movement_spent: int = Field(
        default=0,
        description="Exact movement budget committed by settlement.",
    )
    fixed_costs_committed: bool = Field(
        default=False,
        description="Whether accepted nonmovement and named-resource costs committed.",
    )
    path: Optional[Tuple[Tuple[int, int], ...]] = Field(
        default=None,
        description="Immutable disclosed direct-arc planar geometry.",
    )
    trajectory: MovementTrajectory = Field(
        default=MovementTrajectory.DIRECT_ARC,
        description="Typed trajectory used for the single committed jump leg.",
    )
    termination_reason: MovementTerminationReason = Field(
        default=MovementTerminationReason.COMPLETED,
        description="Reason the accepted jump attempt settled.",
    )

    @model_validator(mode="after")
    def normalize_legacy_jump_endpoints(self) -> Self:
        """Keep old diagnostic constructors coherent without adding authority."""
        if self.requested_end_position is None:
            self.requested_end_position = self.end_position
        if self.objective_end_position is None:
            self.objective_end_position = self.end_position
        return self

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Copy one small Jump proposal without aliasing causal evidence."""
        del deep
        copied = super().model_copy(update=update, deep=True)
        if type(copied.costs) is list:
            copied.costs = [
                BaseCost.model_validate(cost.model_dump())
                if isinstance(cost, BaseCost)
                else deepcopy(cost)
                for cost in copied.costs
            ]
        return copied

    def validate_handler_result(self, result: Event) -> Event:
        """Allow Jump vetoes while freezing its accepted causal transaction."""
        active_proposal = EventQueue.is_active_handler_proposal(result)
        queue_updates: Dict[str, object] = {
            "children_events": list(self.children_events),
            "lineage_children_events": list(self.lineage_children_events),
            "children_lineages": list(self.children_lineages),
            "identified_entity_observer_uuids": _copy_observer_map(
                self.identified_entity_observer_uuids
            ),
            "located_entity_observer_uuids": _copy_observer_map(
                self.located_entity_observer_uuids
            ),
            "located_position_observer_uuids": _copy_observer_map(
                self.located_position_observer_uuids
            ),
        }
        safe_status = (
            result.status_message
            if type(result.status_message) is str or result.status_message is None
            else self.status_message
        )

        def cancellation(status_message: str) -> JumpEvent:
            canceled = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(JumpEvent, canceled.model_copy(update={
                **queue_updates,
                "end_position": self.start_position,
                "objective_end_position": self.start_position,
                "end_elevation_feet": self.start_elevation_feet,
                "termination_reason": MovementTerminationReason.CANCELED,
                "outcome_code": "movement.canceled",
                "use_register": False if active_proposal else self.use_register,
            }))

        if type(result) is not JumpEvent:
            return cancellation("Jump handler returned an incompatible event type")
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and type(result.use_register) is bool
            and (result.status_message is None or type(result.status_message) is str)
        ):
            return cancellation("Jump handler returned malformed queue evidence")

        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(update={"use_register": True})
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return cancellation("Jump handler changed lifecycle evidence")
        if result.canceled:
            return cancellation(safe_status or "Jump canceled by handler")

        allowed_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
            "use_register",
        }
        if any(
            not _exact_event_evidence_equal(
                getattr(self, field_name),
                getattr(result, field_name),
            )
            for field_name in type(self).model_fields
            if field_name not in allowed_fields
        ):
            return cancellation("Jump handler changed immutable causal evidence")

        if (
            not active_proposal
            and result.uuid == self.uuid
            and result.timestamp == self.timestamp
            and result.modified == self.modified
            and safe_status == self.status_message
        ):
            return self

        result_uuid = result.uuid
        changed = safe_status != self.status_message or result.timestamp != self.timestamp
        if result_uuid == self.uuid and changed:
            result_uuid = uuid4()
        return self.model_copy(update={
            **queue_updates,
            "uuid": result_uuid,
            "timestamp": result.timestamp,
            "modified": result.modified or changed,
            "status_message": safe_status,
            "use_register": False if active_proposal else self.use_register,
        })

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return jump path positions relevant to spatial handlers."""
        positions = {self.start_position, self.end_position}
        if self.requested_end_position is not None:
            positions.add(self.requested_end_position)
        if self.path:
            positions.update(self.path)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this jump event."""
        source_name = self.source_entity_name or "Unknown"

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        compact_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {md_color(f'{self.jump_distance}ft', 'green')} to {md_color(end_pos, 'yellow')}"
        verbose_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {start_pos} → {md_color(end_pos, 'green')} ({self.jump_distance}ft)"

        detailed_text = verbose_text
        if self.path and len(self.path) > 2:
            path_str = " -> ".join(f"({p[0]},{p[1]})" for p in self.path)
            detailed_text += f"\n  Air path: {path_str}"

        data = MovementLogData(
            movement_type="jump",
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            start_position=self.start_position,
            end_position=self.end_position,
            path=list(self.path or (self.start_position, self.end_position)),
            distance_feet=(
                self.jump_distance
                if self.end_position != self.start_position
                else 0
            ),
            movement_cost=self.movement_spent,
            start_elevation_feet=self.start_elevation_feet,
            requested_end_elevation_feet=self.requested_end_elevation_feet,
            end_elevation_feet=self.end_elevation_feet,
            requested_end_position=self.requested_end_position,
            objective_end_position=self.objective_end_position,
            termination_reason=self.termination_reason.value,
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=True
        )

class ShoveEvent(ActionEvent):
    """Event payload for a BG3-style shove action.

    Shove is a BG3-style bonus action that pushes adjacent enemies.
    Key mechanics:
    - Cost: Bonus Action
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive skill DC
    - Allies: Auto-succeed (no check required)
    - Weight limit: Strength score x 12 kilograms
    """

    name: str = Field(default="Shove", description="Human-readable shove event label.")
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized shove costs.")
    target_weight: int = Field(default=0, description="Target's weight in pounds")
    max_shove_weight: int = Field(default=0, description="Maximum weight shover can push in pounds.")
    shover_athletics: Optional[ModifiableValue] = Field(default=None, description="Shover's Athletics bonus")
    target_passive: int = Field(default=10, description="Target's passive Athletics or Acrobatics")
    target_resistance_skill: str = Field(default="athletics", description="Target skill used for passive resistance.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Shover's Athletics check roll")
    contest_success: Optional[bool] = Field(default=None, description="Whether the shove contest succeeded.")
    push_distance: int = Field(default=0, description="Distance actually pushed in feet.")
    push_direction: Tuple[int, int] = Field(default=(0, 0), description="Push direction as grid delta.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target's final position after push.")
    knocked_prone: bool = Field(default=False, description="Whether target was knocked prone instead of pushed.")
    blocked_by: Optional[str] = Field(default=None, description="Obstacle or entity that blocked the push.")
    is_ally: bool = Field(default=False, description="Whether target is an ally and auto-succeeds.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return final shove position relevant to spatial handlers."""
        positions = super().get_affected_positions()
        if self.end_position:
            positions.add(self.end_position)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for a shove event."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        if self.contest_success is False:
            compact_text = f"{md_color(source_name, 'cyan')} fails to shove {md_color(target_name, 'yellow')}"
        elif self.knocked_prone:
            compact_text = f"{md_color(source_name, 'cyan')} knocks {md_color(target_name, 'yellow')} {md_color('prone', 'red')}!"
        elif self.push_distance > 0:
            pos_str = f"→ {self.end_position}" if self.end_position else ""
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} {md_color(f'{self.push_distance}ft', 'green')} {pos_str}"
        else:
            blocked_suffix = f" (blocked by {self.blocked_by})" if self.blocked_by else " (blocked)"
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')}{blocked_suffix}"

        verbose_text = compact_text
        if not self.is_ally and self.dice_roll is not None:
            roll_total = self.dice_roll.total
            success_str = md_color("success", "green") if self.contest_success else md_color("fail", "red")
            verbose_text += f"\n  Athletics: d20({md_color(str(roll_total), 'cyan')}) vs DC {self.target_passive} → {success_str}"
        elif self.is_ally:
            verbose_text += f" ({md_color('ally', 'green')})"

        detailed_text = verbose_text
        if self.contest_success:
            if self.knocked_prone:
                detailed_text += f"\n  Effect: Target knocked {md_color('prone', 'red')}"
            else:
                detailed_text += f"\n  Direction: {self.push_direction}"
                detailed_text += f"\n  Weight: {self.target_weight}lbs (max: {self.max_shove_weight}lbs)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "action_type": "shove",
                "target_weight": self.target_weight,
                "max_shove_weight": self.max_shove_weight,
                "contest_success": self.contest_success,
                "push_distance": self.push_distance,
                "push_direction": list(self.push_direction),
                "end_position": list(self.end_position) if self.end_position else None,
                "knocked_prone": self.knocked_prone,
                "blocked_by": self.blocked_by,
                "is_ally": self.is_ally
            },
            success=self.contest_success or False
        )

class DragonbornBreathWeaponEvent(ActionEvent):
    """Cold typed facts produced by one Dragonborn Breath Weapon use."""

    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: AbilityName
    save_dc: int = Field(ge=0)
    save_success: bool | None = None
    save_roll: DiceRoll | None = None
    damage_dice_count: int = Field(ge=1)
    damages: list[Damage] = Field(default_factory=list)
    damage_rolls: list[DiceRoll] = Field(default_factory=list)

class CounterspellReactionEvent(ActionEvent):
    """Observable resolution of one Counterspell reaction."""

    name: str = Field(default="Counterspell", description="Reaction event name.")
    event_type: EventType = Field(
        default=EventType.TRIGGER_EVENT,
        description="Reaction event category.",
    )
    triggered_event_uuid: UUID = Field(
        description="Incoming spell event version that triggered the reaction.",
    )
    triggered_lineage_uuid: UUID = Field(
        description="Incoming spell lineage interrupted or challenged.",
    )
    incoming_spell_name: str = Field(
        description="Display name of the incoming spell.",
    )
    incoming_spell_level: int = Field(
        ge=0,
        le=9,
        description="Level of the incoming cast.",
    )
    counterspell_slot_level: int = Field(
        ge=3,
        le=9,
        description="Slot level spent on Counterspell.",
    )
    automatic: bool = Field(
        description="Whether the selected slot guarantees interruption.",
    )
    check_total: Optional[int] = Field(
        default=None,
        description="Spellcasting check total when required.",
    )
    check_dc: Optional[int] = Field(
        default=None,
        description="Spellcasting check DC when required.",
    )
    succeeded: bool = Field(
        description="Whether Counterspell interrupted the incoming spell.",
    )
    outcome_code: str = type_cast(
        str,
        Field(
            min_length=1,
            description="Stable Counterspell result code matching succeeded.",
        ),
    )
    reaction_behavior_id: str = Field(
        default="reaction.spell.counterspell",
        min_length=1,
        description="Direct Counterspell reaction identity.",
    )
    incoming_spell_behavior_id: str = Field(
        default="action.unclassified",
        min_length=1,
        description="Direct semantic identity of the interrupted spell.",
    )

    @model_validator(mode="after")
    def validate_counterspell_resolution(
        self,
    ) -> "CounterspellReactionEvent":
        """Reject contradictory reaction, roll, and outcome-code facts."""
        if self.reaction_behavior_id != self.behavior_id:
            raise ValueError(
                "reaction behavior ID must match the action event behavior ID",
            )

        expected_outcome_code = (
            COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
            if self.succeeded
            else COUNTERSPELL_FAILURE_OUTCOME_CODE
        )
        if self.outcome_code != expected_outcome_code:
            raise ValueError(
                "Counterspell outcome code contradicts its success result",
            )

        if self.automatic:
            if self.counterspell_slot_level < self.incoming_spell_level:
                raise ValueError(
                    "automatic Counterspell requires a sufficient slot",
                )
            if not self.succeeded:
                raise ValueError("automatic Counterspell must succeed")
            if self.check_total is not None or self.check_dc is not None:
                raise ValueError(
                    "automatic Counterspell forbids check evidence",
                )
            return self

        if self.counterspell_slot_level >= self.incoming_spell_level:
            raise ValueError(
                "checked Counterspell requires a lower-level slot",
            )
        if self.check_total is None or self.check_dc is None:
            raise ValueError(
                "checked Counterspell requires total and DC",
            )
        if self.check_dc != 10 + self.incoming_spell_level:
            raise ValueError(
                "Counterspell check DC must equal 10 plus spell level",
            )
        if self.succeeded != (self.check_total >= self.check_dc):
            raise ValueError("Counterspell success contradicts its check")
        return self

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a typed, subjectivity-filterable reaction log."""
        if self.canceled:
            return None
        counterspeller_name = self.source_entity_name or "Unknown"
        original_caster_name = self.target_entity_name or "Unknown"
        result_text = "interrupts" if self.succeeded else "fails to interrupt"
        compact = (
            f"{counterspeller_name} uses Counterspell and {result_text} "
            f"{original_caster_name}'s {self.incoming_spell_name}"
        )
        data = SpellInterruptionLogData(
            outcome_code=self.outcome_code,
            counterspeller_name=counterspeller_name,
            counterspeller_uuid=str(self.source_entity_uuid),
            original_caster_name=original_caster_name,
            original_caster_uuid=str(self.target_entity_uuid),
            spell_name=self.incoming_spell_name,
            incoming_spell_level=self.incoming_spell_level,
            counterspell_slot_level=self.counterspell_slot_level,
            automatic=self.automatic,
            check_total=self.check_total,
            check_dc=self.check_dc,
            succeeded=self.succeeded,
            reaction_behavior_id=self.reaction_behavior_id,
            incoming_spell_behavior_id=(
                self.incoming_spell_behavior_id
            ),
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_INTERRUPTION,
            source_name=counterspeller_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=original_caster_name,
            target_uuid=str(self.target_entity_uuid),
            compact=compact,
            verbose=compact,
            detailed=compact,
            data=data.model_dump(mode="json"),
            success=self.succeeded,
        )

    def validate_handler_result(self, result: Event) -> Event:
        """Cancel an evidence or event-type rewrite before queue storage."""
        evidence = _CounterspellEvidenceSnapshot.capture(self)
        if (
            type(result) is not CounterspellReactionEvent
            or not isinstance(result, CounterspellReactionEvent)
            or not self.handler_result_preserves_lifecycle(result)
            or not evidence.matches(result)
        ):
            return self.invalid_handler_result_cancellation(
                result,
                status_message=(
                    "Counterspell evidence or lifecycle changed after "
                    "resolution."
                ),
            )
        return result

@dataclass(frozen=True)
class _CounterspellEvidenceSnapshot:
    """Immutable resolution and attribution accepted at declaration."""

    name: str
    event_type: EventType
    lineage_uuid: UUID
    parent_event: Optional[UUID]
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID]
    outcome_source_entity_uuid: Optional[UUID]
    source_entity_name: Optional[str]
    target_entity_name: Optional[str]
    triggered_event_uuid: UUID
    triggered_lineage_uuid: UUID
    incoming_spell_name: str
    incoming_spell_level: int
    counterspell_slot_level: int
    automatic: bool
    check_total: Optional[int]
    check_dc: Optional[int]
    succeeded: bool
    outcome_code: str
    reaction_behavior_id: str
    incoming_spell_behavior_id: str
    behavior_id: str
    provided_by_id: str
    origin_root_id: Optional[str]

    @classmethod
    def capture(
        cls,
        event: CounterspellReactionEvent,
    ) -> "_CounterspellEvidenceSnapshot":
        """Capture every fact handlers must not rewrite after resolution."""
        return cls(
            name=event.name,
            event_type=event.event_type,
            lineage_uuid=event.lineage_uuid,
            parent_event=event.parent_event,
            source_entity_uuid=event.source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            outcome_source_entity_uuid=event.outcome_source_entity_uuid,
            source_entity_name=event.source_entity_name,
            target_entity_name=event.target_entity_name,
            triggered_event_uuid=event.triggered_event_uuid,
            triggered_lineage_uuid=event.triggered_lineage_uuid,
            incoming_spell_name=event.incoming_spell_name,
            incoming_spell_level=event.incoming_spell_level,
            counterspell_slot_level=event.counterspell_slot_level,
            automatic=event.automatic,
            check_total=event.check_total,
            check_dc=event.check_dc,
            succeeded=event.succeeded,
            outcome_code=event.outcome_code,
            reaction_behavior_id=event.reaction_behavior_id,
            incoming_spell_behavior_id=event.incoming_spell_behavior_id,
            behavior_id=event.behavior_id,
            provided_by_id=event.provided_by_id,
            origin_root_id=event.origin_root_id,
        )

    def event_updates(self) -> Dict[str, Any]:
        """Return the exact facts used to close a rewritten lifecycle."""
        return {
            "name": self.name,
            "event_type": self.event_type,
            "lineage_uuid": self.lineage_uuid,
            "parent_event": self.parent_event,
            "source_entity_uuid": self.source_entity_uuid,
            "target_entity_uuid": self.target_entity_uuid,
            "outcome_source_entity_uuid": self.outcome_source_entity_uuid,
            "source_entity_name": self.source_entity_name,
            "target_entity_name": self.target_entity_name,
            "triggered_event_uuid": self.triggered_event_uuid,
            "triggered_lineage_uuid": self.triggered_lineage_uuid,
            "incoming_spell_name": self.incoming_spell_name,
            "incoming_spell_level": self.incoming_spell_level,
            "counterspell_slot_level": self.counterspell_slot_level,
            "automatic": self.automatic,
            "check_total": self.check_total,
            "check_dc": self.check_dc,
            "succeeded": self.succeeded,
            "outcome_code": self.outcome_code,
            "reaction_behavior_id": self.reaction_behavior_id,
            "incoming_spell_behavior_id": self.incoming_spell_behavior_id,
            "behavior_id": self.behavior_id,
            "provided_by_id": self.provided_by_id,
            "origin_root_id": self.origin_root_id,
        }

    def matches(self, event: CounterspellReactionEvent) -> bool:
        """Return whether a phase preserves exact values and runtime types."""
        return all(
            type(getattr(event, field_name)) is type(expected_value)
            and getattr(event, field_name) == expected_value
            for field_name, expected_value in self.event_updates().items()
        )
