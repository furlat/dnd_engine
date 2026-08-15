"""Canonical engine-event to subjective-presentation projection.

The mapper consumes an exact, contiguous causal batch of engine event versions
and emits one route-free subjective replication frame.  It never serializes an
engine event.  Identity and exact entity-position facts are admitted only from
the event-time observer grants carried by that exact event version (controlled
entities are the sole unconditional exception).

Technical event-tree nodes are omitted.  Their visible semantic descendants
are attached to the nearest compatible delivered node, producing a closed
projection-native graph whose identities contain no engine lineage UUIDs.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypeAlias, cast
from uuid import UUID

from dnd.actions import (
    AttackEvent,
    JumpEvent,
    MovementEvent,
    ShoveEvent,
    SpellEvent,
    TraverseConnectorEvent,
)
from dnd.core.base_block import MovementMode
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.core.action_types import ActionPresentationKind
from dnd.core.base_actions import ActionEvent
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.combat_log import position_evidence_key
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.identities import ContentRef
from dnd.core.content.runtime import (
    BehaviorBinding,
    EffectiveHandlerPresentation,
    HandlerDispatchOutcome,
)
from dnd.core.dice import AttackOutcome as EngineAttackOutcome
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    DamageAppliedEvent,
    DeathSaveEvent,
    EncounterEndEvent,
    EncounterStartEvent,
    Event,
    EventPhase,
    EventType,
    ForcedMovementEvent,
    HealEvent,
    InstantDeathEvent,
    LifeStateChangeEvent,
    MovementTrajectory,
    ReviveEvent,
    RoundEndEvent,
    RoundStartEvent,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialEffectChangeEvent,
    StepMovementEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.core.item_types import ItemPresentationKind
from dnd.core.presentation_geometry import (
    ConePresentationGeometry,
    CubePresentationGeometry,
    CylinderPresentationGeometry,
    LinePresentationGeometry,
    SpherePresentationGeometry,
)
from dnd.core.spatial_effect_types import (
    SpatialEffectChangeOperation,
    SpatialEffectLayer,
)
from dnd.core.traversal_connectors import (
    CONNECTOR_AUTHORED_ID_PATTERN,
    CONNECTOR_PRESENTATION_KEY_PATTERN,
    TraversalConnectorKind,
)
from dnd.spells.abjuration import CounterspellReactionEvent
from server.player_replication.journal import SubjectiveFrameProjectionContext
from server.player_replication.presentation import (
    PresentationNodeCoordinates,
    PresentationNodeDraft,
    materialize_presentation_graph,
)
from server.player_replication_contract import (
    ActionPresentationCue,
    ActorVisualSlot,
    AreaGeometry,
    AttackDelivery,
    AttackOutcome,
    AttackPresentationCue,
    ConditionOperation,
    ConditionPresentationCue,
    BehaviorPresentationRole,
    ConeAreaGeometry,
    CounterspellAutomaticSuccess,
    CounterspellCheckFailure,
    CounterspellCheckSuccess,
    CounterspellPresentationCue,
    CounterspellResolution,
    CubeAreaGeometry,
    CylinderAreaGeometry,
    DamagePresentationCue,
    DeathSaveOutcome,
    DoorPresentationCue,
    DoorStatePatch,
    EffectiveLightCell,
    EncounterPresentationCue,
    EncounterTransition,
    EntityVisualLoadout,
    EquipmentPresentationCue,
    ForcedMovementCause,
    ForcedMovementPresentationCue,
    HealPresentationCue,
    ItemActionKind,
    ItemActionPresentationCue,
    LifecycleCauseKind,
    LifecycleCausePresentationCue,
    LifeStatePresentationCue,
    LightPresentationCue,
    LineAreaGeometry,
    ConnectorPresentationIdentity,
    LocomotionAnchor,
    LocomotionFamily,
    LocomotionTrajectory,
    MovementEndpointOutcome,
    MovementPresentationCue,
    PlayerReplicationWatermarks,
    PresentationDamageType,
    PresentationContentAttribution,
    PresentationProjectile,
    PresentationSpellSchool,
    PresentationWeaponSlot,
    ShoveOutcome,
    ShovePresentationCue,
    RootedBehaviorPresentationAttribution,
    SourceItemPresentationAttribution,
    SphereAreaGeometry,
    SpellApplicationOutcome,
    SpellDelivery,
    SpellPresentationCue,
    SpellTargetPresentation,
    SpatialEffectPresentationCue,
    SubjectivePerspective,
    SubjectivePresentationCue,
    SubjectiveReplicationFrame,
    SubjectiveWorldPatch,
    VisualLoadoutReplacePatch,
    UnrootedBehaviorPresentationAttribution,
)


class SubjectiveEventProjectionError(ValueError):
    """Raised when the source batch cannot prove exact, safe projection."""


@dataclass(frozen=True)
class ProjectedEventSlot:
    """One exact one-based EventQueue cursor paired with its typed event version."""

    source_event_cursor: int
    event: Event

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_event_cursor, bool)
            or not isinstance(self.source_event_cursor, int)
            or self.source_event_cursor < 1
        ):
            raise ValueError("source event cursor must be a positive integer")
        if not isinstance(self.event, Event):
            raise TypeError("projected event slot requires an engine Event")


class MovementRootDeliveryScope(str, Enum):
    """Delivery topology frozen when the accepted root EFFECT is stored."""

    EXPLICIT_ACTION_BATCH = "explicit_action_batch"
    IMMEDIATE_SINGLETON_SEQUENCE = "immediate_singleton_sequence"


MAX_MOVEMENT_ROOT_CONTEXTS = 64
MAX_ROOT_EFFECT_ALIASES_PER_LINEAGE = 16


class MovementRootKind(str, Enum):
    """Exact engine root family retained without an Event reference."""

    PATH = "path"
    JUMP = "jump"
    CONNECTOR = "connector"


@dataclass(frozen=True, slots=True)
class MovementRootContextBase:
    """Immutable common evidence copied once from one accepted root EFFECT."""

    generation_id: str
    first_effect_source_cursor: int
    first_effect_uuid: UUID
    root_kind: MovementRootKind
    phase: EventPhase
    source_entity_uuid: UUID
    lineage_uuid: UUID
    identified_source_observer_uuids: frozenset[str]
    delivery_scope: MovementRootDeliveryScope

    def __post_init__(self) -> None:
        _validate_movement_root_context(cast(MovementRootProjectionContext, self))


@dataclass(frozen=True, slots=True)
class PathMovementRootContext(MovementRootContextBase):
    movement_mode: MovementMode
    trajectory: MovementTrajectory
    admitted_path: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class JumpRootContext(MovementRootContextBase):
    trajectory: MovementTrajectory
    takeoff_position: tuple[int, int]
    landing_position: tuple[int, int]
    takeoff_elevation_feet: int
    landing_elevation_feet: int
    disclosed_arc: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class ConnectorRootContext(MovementRootContextBase):
    source_position: tuple[int, int]
    destination_position: tuple[int, int]
    source_elevation_feet: int
    destination_elevation_feet: int
    connector_uuid: UUID
    connector_authored_id: str
    connector_kind: TraversalConnectorKind
    connector_presentation_key: str
    connector_revision: int


MovementRootProjectionContext: TypeAlias = (
    PathMovementRootContext | JumpRootContext | ConnectorRootContext
)


@dataclass(frozen=True, slots=True)
class MovementRootEffectAlias:
    """One accepted root EFFECT UUID and its exact stored source cursor."""

    effect_uuid: UUID
    source_event_cursor: int

    def __post_init__(self) -> None:
        if type(self.effect_uuid) is not UUID:
            raise TypeError("movement root alias UUID must be an exact UUID")
        if (
            type(self.source_event_cursor) is not int
            or self.source_event_cursor < 1
        ):
            raise ValueError("movement root alias cursor must be a positive integer")


@dataclass(frozen=True, slots=True)
class MovementRootProjectionView:
    """Bounded immutable context plus accepted status-only EFFECT aliases."""

    context: MovementRootProjectionContext
    effect_uuid_aliases: tuple[MovementRootEffectAlias, ...]

    def __post_init__(self) -> None:
        if type(self.context) not in {
            PathMovementRootContext,
            JumpRootContext,
            ConnectorRootContext,
        }:
            raise TypeError("movement root view requires one closed context variant")
        if type(self.effect_uuid_aliases) is not tuple:
            raise TypeError("movement root aliases must be an immutable tuple")
        if not 1 <= len(self.effect_uuid_aliases) <= MAX_ROOT_EFFECT_ALIASES_PER_LINEAGE:
            raise ValueError("movement root aliases must contain between 1 and 16 entries")
        if any(
            type(alias) is not MovementRootEffectAlias
            for alias in self.effect_uuid_aliases
        ):
            raise TypeError("movement root aliases require exact alias records")
        uuids = tuple(alias.effect_uuid for alias in self.effect_uuid_aliases)
        cursors = tuple(alias.source_event_cursor for alias in self.effect_uuid_aliases)
        if len(set(uuids)) != len(uuids) or len(set(cursors)) != len(cursors):
            raise ValueError("movement root aliases must have unique UUIDs and cursors")
        first = self.effect_uuid_aliases[0]
        if (
            first.effect_uuid != self.context.first_effect_uuid
            or first.source_event_cursor != self.context.first_effect_source_cursor
        ):
            raise ValueError("movement root alias one must be the captured first EFFECT")


def _validate_movement_root_context(
    context: MovementRootProjectionContext,
) -> None:
    """Reject manually constructed context records that bypass capture validation."""
    if type(context.generation_id) is not str or not context.generation_id:
        raise ValueError("movement root generation must be nonempty")
    if (
        type(context.first_effect_source_cursor) is not int
        or context.first_effect_source_cursor < 1
    ):
        raise ValueError("movement root first EFFECT cursor must be positive")
    if type(context.first_effect_uuid) is not UUID:
        raise TypeError("movement root first EFFECT UUID must be exact")
    if type(context.phase) is not EventPhase or context.phase is not EventPhase.EFFECT:
        raise ValueError("movement root context must describe EFFECT")
    if type(context.source_entity_uuid) is not UUID:
        raise TypeError("movement root source UUID must be exact")
    if type(context.lineage_uuid) is not UUID:
        raise TypeError("movement root lineage UUID must be exact")
    if (
        type(context.identified_source_observer_uuids) is not frozenset
        or any(
            type(observer_uuid) is not str
            for observer_uuid in context.identified_source_observer_uuids
        )
    ):
        raise TypeError("movement root identity grants must be exact strings")
    if type(context.delivery_scope) is not MovementRootDeliveryScope:
        raise TypeError("movement root delivery scope must be exact")

    if type(context) is PathMovementRootContext:
        if context.root_kind is not MovementRootKind.PATH:
            raise ValueError("path context has the wrong root kind")
        if type(context.movement_mode) is not MovementMode:
            raise TypeError("path context movement mode must be exact")
        if (
            type(context.trajectory) is not MovementTrajectory
            or context.trajectory is not MovementTrajectory.PATH
        ):
            raise ValueError("path context must use PATH trajectory")
        _require_position_path(
            context.admitted_path,
            field_name="movement root admitted path",
            minimum_length=1,
        )
        return
    if type(context) is JumpRootContext:
        if context.root_kind is not MovementRootKind.JUMP:
            raise ValueError("jump context has the wrong root kind")
        if (
            type(context.trajectory) is not MovementTrajectory
            or context.trajectory is not MovementTrajectory.DIRECT_ARC
        ):
            raise ValueError("jump context must use DIRECT_ARC trajectory")
        _require_position(context.takeoff_position, field_name="jump takeoff")
        _require_position(context.landing_position, field_name="jump landing")
        _require_elevation(
            context.takeoff_elevation_feet,
            field_name="jump takeoff elevation",
        )
        _require_elevation(
            context.landing_elevation_feet,
            field_name="jump landing elevation",
        )
        _require_position_path(
            context.disclosed_arc,
            field_name="jump disclosed arc",
            minimum_length=2,
        )
        return
    if type(context) is ConnectorRootContext:
        if context.root_kind is not MovementRootKind.CONNECTOR:
            raise ValueError("connector context has the wrong root kind")
        _require_position(context.source_position, field_name="connector source")
        _require_position(
            context.destination_position,
            field_name="connector destination",
        )
        if context.source_position == context.destination_position:
            raise ValueError("connector context endpoints must be distinct")
        _require_elevation(
            context.source_elevation_feet,
            field_name="connector source elevation",
        )
        _require_elevation(
            context.destination_elevation_feet,
            field_name="connector destination elevation",
        )
        if type(context.connector_uuid) is not UUID:
            raise TypeError("connector context UUID must be exact")
        if (
            type(context.connector_authored_id) is not str
            or re.fullmatch(
                CONNECTOR_AUTHORED_ID_PATTERN,
                context.connector_authored_id,
            )
            is None
        ):
            raise ValueError("connector context authored ID is malformed")
        if type(context.connector_kind) is not TraversalConnectorKind:
            raise TypeError("connector context kind must be exact")
        if (
            type(context.connector_presentation_key) is not str
            or re.fullmatch(
                CONNECTOR_PRESENTATION_KEY_PATTERN,
                context.connector_presentation_key,
            )
            is None
        ):
            raise ValueError("connector context presentation key is malformed")
        if (
            type(context.connector_revision) is not int
            or context.connector_revision < 1
        ):
            raise ValueError("connector context revision must be positive")
        return
    raise TypeError("movement root context requires one closed context variant")


@dataclass(frozen=True)
class CausalEventBatch:
    """One exact source window plus already-authorized typed world mutations.

    ``slots`` contains every event version in the consumed source interval.  A
    batch whose events are all hidden still advances ``through_source_event_cursor``
    and produces an empty presentation transaction.  ``patches`` are injected
    by the canonical world projector after it has diffed the same atomic state
    boundary; the event mapper never consults a live registry to reconstruct
    them.
    """

    slots: tuple[ProjectedEventSlot, ...]
    through_source_event_cursor: int
    patches: tuple[SubjectiveWorldPatch, ...] = field(default_factory=tuple)
    movement_root_contexts: tuple[MovementRootProjectionView, ...] = field(
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.through_source_event_cursor, bool)
            or not isinstance(self.through_source_event_cursor, int)
            or self.through_source_event_cursor < 0
        ):
            raise ValueError("source batch boundary must be a nonnegative integer")
        cursors = tuple(slot.source_event_cursor for slot in self.slots)
        if cursors:
            expected = tuple(range(cursors[0], cursors[-1] + 1))
            if cursors != expected:
                raise ValueError("source batch event slots must be contiguous and ordered")
            if cursors[-1] != self.through_source_event_cursor:
                raise ValueError("source batch boundary must equal its final event slot")
        event_uuids = tuple(slot.event.uuid for slot in self.slots)
        if len(event_uuids) != len(set(event_uuids)):
            raise ValueError("source batch event version UUIDs must be unique")
        if type(self.movement_root_contexts) is not tuple:
            raise TypeError("movement root contexts must be an immutable tuple")
        lineages: set[UUID] = set()
        aliases: set[UUID] = set()
        alias_cursors: set[int] = set()
        generations: set[str] = set()
        for view in self.movement_root_contexts:
            if type(view) is not MovementRootProjectionView:
                raise TypeError("movement root contexts require exact projection views")
            context = view.context
            if context.lineage_uuid in lineages:
                raise ValueError("movement root lineages must have unique owners")
            lineages.add(context.lineage_uuid)
            generations.add(context.generation_id)
            for alias in view.effect_uuid_aliases:
                if alias.effect_uuid in aliases or alias.source_event_cursor in alias_cursors:
                    raise ValueError("movement root aliases conflict across lineages")
                if alias.source_event_cursor > self.through_source_event_cursor:
                    raise ValueError("movement root alias exceeds the batch watermark")
                aliases.add(alias.effect_uuid)
                alias_cursors.add(alias.source_event_cursor)
        if len(generations) > 1:
            raise ValueError("movement root contexts must belong to one generation")
        if len(self.movement_root_contexts) > MAX_MOVEMENT_ROOT_CONTEXTS:
            raise ValueError("movement root context capacity exceeded")


def capture_movement_root_context(
    event: Event,
    *,
    source_event_cursor: int,
    generation_id: str,
    delivery_scope: MovementRootDeliveryScope,
) -> MovementRootProjectionView:
    """Copy one accepted movement-root EFFECT into closed immutable evidence."""
    _require_root_common_evidence(
        event,
        source_event_cursor=source_event_cursor,
        generation_id=generation_id,
        delivery_scope=delivery_scope,
    )
    common = {
        "generation_id": generation_id,
        "first_effect_source_cursor": source_event_cursor,
        "first_effect_uuid": event.uuid,
        "phase": EventPhase.EFFECT,
        "source_entity_uuid": event.source_entity_uuid,
        "lineage_uuid": event.lineage_uuid,
        "identified_source_observer_uuids": _root_source_identity_grants(event),
        "delivery_scope": delivery_scope,
    }
    context: MovementRootProjectionContext
    if type(event) is MovementEvent:
        if type(event.movement_mode) is not MovementMode:
            raise SubjectiveEventProjectionError("movement root has malformed mode")
        if event.trajectory is not MovementTrajectory.PATH:
            raise SubjectiveEventProjectionError("movement root must use PATH trajectory")
        context = PathMovementRootContext(
            **common,
            root_kind=MovementRootKind.PATH,
            movement_mode=event.movement_mode,
            trajectory=event.trajectory,
            admitted_path=_require_position_path(
                event.path,
                field_name="movement root admitted path",
                minimum_length=1,
            ),
        )
    elif type(event) is JumpEvent:
        if event.trajectory is not MovementTrajectory.DIRECT_ARC:
            raise SubjectiveEventProjectionError("jump root must use DIRECT_ARC trajectory")
        if event.requested_end_position is None:
            raise SubjectiveEventProjectionError("jump root requires an accepted landing")
        context = JumpRootContext(
            **common,
            root_kind=MovementRootKind.JUMP,
            trajectory=event.trajectory,
            takeoff_position=_require_position(
                event.start_position,
                field_name="jump takeoff",
            ),
            landing_position=_require_position(
                event.requested_end_position,
                field_name="jump landing",
            ),
            takeoff_elevation_feet=_require_elevation(
                event.start_elevation_feet,
                field_name="jump takeoff elevation",
            ),
            landing_elevation_feet=_require_elevation(
                event.requested_end_elevation_feet,
                field_name="jump landing elevation",
            ),
            disclosed_arc=_require_position_path(
                event.path,
                field_name="jump disclosed arc",
                minimum_length=2,
            ),
        )
    elif type(event) is TraverseConnectorEvent:
        if type(event.connector_uuid) is not UUID:
            raise SubjectiveEventProjectionError("connector root has malformed UUID")
        if (
            type(event.connector_authored_id) is not str
            or re.fullmatch(
                CONNECTOR_AUTHORED_ID_PATTERN,
                event.connector_authored_id,
            ) is None
        ):
            raise SubjectiveEventProjectionError("connector root has malformed authored ID")
        if type(event.connector_kind) is not TraversalConnectorKind:
            raise SubjectiveEventProjectionError("connector root has malformed kind")
        if (
            type(event.connector_presentation_key) is not str
            or re.fullmatch(
                CONNECTOR_PRESENTATION_KEY_PATTERN,
                event.connector_presentation_key,
            ) is None
        ):
            raise SubjectiveEventProjectionError(
                "connector root has malformed presentation key"
            )
        if type(event.connector_revision) is not int or event.connector_revision < 1:
            raise SubjectiveEventProjectionError("connector root has malformed revision")
        context = ConnectorRootContext(
            **common,
            root_kind=MovementRootKind.CONNECTOR,
            source_position=_require_position(
                event.start_position,
                field_name="connector source",
            ),
            destination_position=_require_position(
                event.requested_end_position,
                field_name="connector destination",
            ),
            source_elevation_feet=_require_elevation(
                event.start_elevation_feet,
                field_name="connector source elevation",
            ),
            destination_elevation_feet=_require_elevation(
                event.requested_end_elevation_feet,
                field_name="connector destination elevation",
            ),
            connector_uuid=event.connector_uuid,
            connector_authored_id=event.connector_authored_id,
            connector_kind=event.connector_kind,
            connector_presentation_key=event.connector_presentation_key,
            connector_revision=event.connector_revision,
        )
    else:
        raise SubjectiveEventProjectionError(
            "movement root capture requires MovementEvent, JumpEvent, or TraverseConnectorEvent"
        )
    return MovementRootProjectionView(
        context=context,
        effect_uuid_aliases=(
            MovementRootEffectAlias(
                effect_uuid=event.uuid,
                source_event_cursor=source_event_cursor,
            ),
        ),
    )


def add_movement_root_effect_alias(
    view: MovementRootProjectionView,
    event: Event,
    *,
    source_event_cursor: int,
) -> MovementRootProjectionView:
    """Return a view containing one mechanically identical status-only alias."""
    if type(view) is not MovementRootProjectionView:
        raise TypeError("movement root aliasing requires an exact projection view")
    if not _movement_root_event_matches_context(view.context, event):
        raise SubjectiveEventProjectionError(
            "movement root EFFECT alias changed frozen mechanical or identity evidence"
        )
    alias = MovementRootEffectAlias(
        effect_uuid=event.uuid,
        source_event_cursor=source_event_cursor,
    )
    for existing in view.effect_uuid_aliases:
        if existing.effect_uuid == alias.effect_uuid:
            if existing.source_event_cursor != alias.source_event_cursor:
                raise SubjectiveEventProjectionError(
                    "movement root EFFECT UUID was reused at another cursor"
                )
            return view
        if existing.source_event_cursor == alias.source_event_cursor:
            raise SubjectiveEventProjectionError(
                "movement root EFFECT cursor is already owned by another UUID"
            )
    if len(view.effect_uuid_aliases) >= MAX_ROOT_EFFECT_ALIASES_PER_LINEAGE:
        raise SubjectiveEventProjectionError("movement root EFFECT alias capacity exceeded")
    return MovementRootProjectionView(
        context=view.context,
        effect_uuid_aliases=(*view.effect_uuid_aliases, alias),
    )


def _require_root_common_evidence(
    event: Event,
    *,
    source_event_cursor: int,
    generation_id: str,
    delivery_scope: MovementRootDeliveryScope,
) -> None:
    if type(source_event_cursor) is not int or source_event_cursor < 1:
        raise SubjectiveEventProjectionError("movement root cursor must be positive")
    if type(generation_id) is not str or not generation_id:
        raise SubjectiveEventProjectionError("movement root generation must be nonempty")
    if type(delivery_scope) is not MovementRootDeliveryScope:
        raise SubjectiveEventProjectionError("movement root delivery scope is malformed")
    if (
        type(event) not in {MovementEvent, JumpEvent, TraverseConnectorEvent}
        or event.phase is not EventPhase.EFFECT
        or type(event.canceled) is not bool
        or event.canceled
        or event.canceled_from_phase is not None
        or event.event_type is not EventType.MOVEMENT
        or type(event.uuid) is not UUID
        or type(event.source_entity_uuid) is not UUID
        or type(event.lineage_uuid) is not UUID
    ):
        raise SubjectiveEventProjectionError(
            "movement root capture requires an exact accepted EFFECT event"
        )


def _root_source_identity_grants(event: Event) -> frozenset[str]:
    grants_by_entity = event.identified_entity_observer_uuids
    if type(grants_by_entity) is not dict:
        raise SubjectiveEventProjectionError("movement root identity grants are malformed")
    grants = grants_by_entity.get(str(event.source_entity_uuid), set())
    if type(grants) is not set or any(type(observer) is not str for observer in grants):
        raise SubjectiveEventProjectionError("movement root source identity grant is malformed")
    return frozenset(grants)


def _root_source_identity_grants_match(
    event: Event,
    expected: frozenset[str],
) -> bool:
    """Validate alias grant shapes and compare without rebuilding frozen evidence."""
    grants_by_entity = event.identified_entity_observer_uuids
    if type(grants_by_entity) is not dict:
        raise SubjectiveEventProjectionError("movement root identity grants are malformed")
    grants = grants_by_entity.get(str(event.source_entity_uuid), set())
    if type(grants) is not set or any(type(observer) is not str for observer in grants):
        raise SubjectiveEventProjectionError("movement root source identity grant is malformed")
    return grants == expected


def _require_position(
    value: object,
    *,
    field_name: str,
) -> tuple[int, int]:
    if (
        type(value) is not tuple
        or len(value) != 2
        or any(type(component) is not int for component in value)
    ):
        raise SubjectiveEventProjectionError(f"{field_name} is malformed")
    return value


def _require_position_path(
    value: object,
    *,
    field_name: str,
    minimum_length: int,
) -> tuple[tuple[int, int], ...]:
    if type(value) is not tuple or len(value) < minimum_length:
        raise SubjectiveEventProjectionError(f"{field_name} is malformed")
    for position in value:
        _require_position(position, field_name=field_name)
    return cast(tuple[tuple[int, int], ...], value)


def _require_elevation(value: object, *, field_name: str) -> int:
    if type(value) is not int or value % 5 != 0:
        raise SubjectiveEventProjectionError(f"{field_name} is malformed")
    return value


def _movement_root_event_matches_context(
    context: MovementRootProjectionContext,
    event: Event,
) -> bool:
    try:
        _require_root_common_evidence(
            event,
            source_event_cursor=context.first_effect_source_cursor,
            generation_id=context.generation_id,
            delivery_scope=context.delivery_scope,
        )
        if (
            event.source_entity_uuid != context.source_entity_uuid
            or event.lineage_uuid != context.lineage_uuid
            or not _root_source_identity_grants_match(
                event,
                context.identified_source_observer_uuids,
            )
        ):
            return False
        if type(context) is PathMovementRootContext:
            return (
                type(event) is MovementEvent
                and event.movement_mode is context.movement_mode
                and event.trajectory is context.trajectory
                and _require_position_path(
                    event.path,
                    field_name="movement root admitted path",
                    minimum_length=1,
                ) == context.admitted_path
            )
        if type(context) is JumpRootContext:
            return (
                type(event) is JumpEvent
                and event.requested_end_position is not None
                and event.trajectory is context.trajectory
                and _require_position(event.start_position, field_name="jump takeoff")
                == context.takeoff_position
                and _require_position(event.requested_end_position, field_name="jump landing")
                == context.landing_position
                and _require_elevation(event.start_elevation_feet, field_name="jump takeoff elevation")
                == context.takeoff_elevation_feet
                and _require_elevation(event.requested_end_elevation_feet, field_name="jump landing elevation")
                == context.landing_elevation_feet
                and _require_position_path(
                    event.path,
                    field_name="jump disclosed arc",
                    minimum_length=2,
                ) == context.disclosed_arc
            )
        return (
            type(context) is ConnectorRootContext
            and type(event) is TraverseConnectorEvent
            and _require_position(event.start_position, field_name="connector source")
            == context.source_position
            and _require_position(event.requested_end_position, field_name="connector destination")
            == context.destination_position
            and _require_elevation(event.start_elevation_feet, field_name="connector source elevation")
            == context.source_elevation_feet
            and _require_elevation(event.requested_end_elevation_feet, field_name="connector destination elevation")
            == context.destination_elevation_feet
            and type(event.connector_uuid) is UUID
            and event.connector_uuid == context.connector_uuid
            and type(event.connector_authored_id) is str
            and event.connector_authored_id == context.connector_authored_id
            and type(event.connector_kind) is TraversalConnectorKind
            and event.connector_kind is context.connector_kind
            and type(event.connector_presentation_key) is str
            and event.connector_presentation_key == context.connector_presentation_key
            and type(event.connector_revision) is int
            and event.connector_revision == context.connector_revision
        )
    except SubjectiveEventProjectionError:
        return False


class _NodeKind(str, Enum):
    MOVEMENT = "movement"
    ACTION = "action"
    ATTACK = "attack"
    SPELL = "spell"
    COUNTERSPELL = "counterspell"
    ITEM = "item"
    SHOVE = "shove"
    FORCED = "forced"
    DAMAGE = "damage"
    HEAL = "heal"
    LIFECYCLE_CAUSE = "lifecycle_cause"
    LIFE = "life"
    CONDITION = "condition"
    DOOR = "door"
    LIGHT = "light"
    SPATIAL_EFFECT = "spatial_effect"
    EQUIPMENT = "equipment"
    ENCOUNTER = "encounter"


@dataclass(frozen=True)
class _MovementPayload:
    entity_uuid: str
    locomotion_family: LocomotionFamily
    trajectory_family: LocomotionTrajectory
    anchors: tuple[LocomotionAnchor, ...]
    connector: Optional[ConnectorPresentationIdentity]
    endpoint_outcome: MovementEndpointOutcome


@dataclass(frozen=True)
class _ActionPayload:
    actor_uuid: str
    action_name: str
    target_uuids: tuple[str, ...]
    trigger_key: Optional[str] = None


@dataclass(frozen=True)
class _AttackPayload:
    actor_uuid: str
    target_uuid: str
    action_name: str
    outcome: AttackOutcome
    delivery: AttackDelivery
    weapon_slot: PresentationWeaponSlot
    damage_types: tuple[PresentationDamageType, ...]
    projectile_type: Optional[PresentationProjectile]


@dataclass
class _SpellApplication:
    source_lineage: str
    outcome: SpellApplicationOutcome
    target_uuid: Optional[str]
    position: Optional[tuple[int, int]]
    effect_keys: list[str] = field(default_factory=list)


@dataclass
class _SpellPayload:
    actor_uuid: str
    spell_id: str
    spell_name: str
    spell_school: PresentationSpellSchool
    spell_level: int
    delivery: SpellDelivery
    projectile_type: Optional[PresentationProjectile]
    area: Optional[AreaGeometry]
    applications: list[_SpellApplication]


@dataclass(frozen=True)
class _ItemPayload:
    actor_uuid: str
    item_uuid: str
    item_kind: ItemPresentationKind


@dataclass(frozen=True)
class _CounterspellPayload:
    reactor_uuid: str
    incoming_caster_uuid: str
    incoming_spell_level: int
    counterspell_slot_level: int
    resolution: CounterspellResolution


@dataclass(frozen=True)
class _ShovePayload:
    actor_uuid: str
    target_uuid: str
    outcome: ShoveOutcome
    forced_key: Optional[str]
    prone_key: Optional[str]


@dataclass(frozen=True)
class _ForcedPayload:
    entity_uuid: str
    source_uuid: str
    cause: ForcedMovementCause
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    duration_ms: int


@dataclass(frozen=True)
class _DamagePayload:
    source_uuid: Optional[str]
    target_uuid: str
    applied_amount: int
    resulting_hp: int
    damage_types: tuple[PresentationDamageType, ...]


@dataclass(frozen=True)
class _HealPayload:
    source_uuid: Optional[str]
    target_uuid: str
    amount: int
    resulting_hp: int


@dataclass(frozen=True)
class _LifecycleCausePayload:
    entity_uuid: str
    cause_kind: LifecycleCauseKind
    source_uuid: Optional[str]
    death_save_outcome: Optional[DeathSaveOutcome]


@dataclass(frozen=True)
class _LifePayload:
    entity_uuid: str
    previous: LifeState
    current: LifeState
    reason: LifeStateChangeReason


@dataclass(frozen=True)
class _ConditionPayload:
    target_uuid: str
    condition_semantic_key: str
    condition_name: str
    condition_category: Optional[str]
    operation: ConditionOperation


@dataclass(frozen=True)
class _DoorPayload:
    object_uuid: str
    position: tuple[int, int]
    is_open: bool


@dataclass(frozen=True)
class _LightPayload:
    observer_uuid: str
    cells: tuple[EffectiveLightCell, ...]


@dataclass(frozen=True)
class _SpatialEffectPayload:
    effect_uuid: str
    content_ref: ContentRef
    operation: SpatialEffectChangeOperation
    layer: SpatialEffectLayer
    anchor_position: Optional[tuple[int, int]]
    affected_positions: tuple[tuple[int, int], ...]
    previous_positions: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _EquipmentPayload:
    entity_uuid: str
    visual_loadout: EntityVisualLoadout


@dataclass(frozen=True)
class _EncounterPayload:
    encounter_uuid: str
    transition: EncounterTransition
    round_number: int
    acting_entity_uuid: Optional[str]
    reason: Optional[str]
    terminal_barrier: bool
    projected_combatant_uuids: tuple[str, ...]


_Payload = (
    _MovementPayload
    | _ActionPayload
    | _AttackPayload
    | _SpellPayload
    | _CounterspellPayload
    | _ItemPayload
    | _ShovePayload
    | _ForcedPayload
    | _DamagePayload
    | _HealPayload
    | _LifecycleCausePayload
    | _LifePayload
    | _ConditionPayload
    | _DoorPayload
    | _LightPayload
    | _SpatialEffectPayload
    | _EquipmentPayload
    | _EncounterPayload
)


@dataclass
class _NodeSpec:
    key: str
    kind: _NodeKind
    slot: ProjectedEventSlot
    payload: _Payload
    lineage: str
    order_key: tuple[int, ...]
    content_attributions: tuple[PresentationContentAttribution, ...] = ()
    parent_key: Optional[str] = None


@dataclass(frozen=True)
class _SpellRootPresentationAuthority:
    """Frozen requester grants admitted by one exact spell-root lifecycle."""

    runtime_type: type[SpellEvent]
    lineage_uuid: UUID
    source_entity_uuid: UUID
    source_position: tuple[int, int] | None
    spell_id: str
    area_geometry: object
    identified_source_observer_uuids: frozenset[str]
    located_source_observer_uuids: frozenset[str]


def _spell_source_observer_grants(
    event: SpellEvent,
    *,
    located: bool,
) -> frozenset[str]:
    grants_by_entity = (
        event.located_entity_observer_uuids
        if located
        else event.identified_entity_observer_uuids
    )
    if type(grants_by_entity) is not dict:
        raise SubjectiveEventProjectionError(
            "spell root source observer grants are malformed"
        )
    grants = grants_by_entity.get(str(event.source_entity_uuid), set())
    if type(grants) is not set or any(
        type(observer_uuid) is not str for observer_uuid in grants
    ):
        raise SubjectiveEventProjectionError(
            "spell root source observer grant is malformed"
        )
    return frozenset(grants)


def _capture_spell_root_presentation_authority(
    event: SpellEvent,
) -> _SpellRootPresentationAuthority:
    if (
        type(event.lineage_uuid) is not UUID
        or type(event.source_entity_uuid) is not UUID
        or event.event_type is not EventType.CAST_SPELL
        or type(event.phase) is not EventPhase
        or event.phase
        not in {
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        }
        or event.canceled is not False
        or event.canceled_from_phase is not None
        or event.application_index is not None
        or type(event.spell_id) is not str
        or not event.spell_id
    ):
        raise SubjectiveEventProjectionError(
            "spell root presentation authority is malformed"
        )
    source_position = (
        None
        if event.source_position is None
        else _require_position(
            event.source_position,
            field_name="spell root source_position",
        )
    )
    return _SpellRootPresentationAuthority(
        runtime_type=type(event),
        lineage_uuid=event.lineage_uuid,
        source_entity_uuid=event.source_entity_uuid,
        source_position=source_position,
        spell_id=event.spell_id,
        area_geometry=event.area_geometry,
        identified_source_observer_uuids=_spell_source_observer_grants(
            event,
            located=False,
        ),
        located_source_observer_uuids=_spell_source_observer_grants(
            event,
            located=True,
        ),
    )


def _spell_root_authority_signature_matches(
    left: _SpellRootPresentationAuthority,
    right: _SpellRootPresentationAuthority,
) -> bool:
    return (
        left.runtime_type is right.runtime_type
        and left.lineage_uuid == right.lineage_uuid
        and left.source_entity_uuid == right.source_entity_uuid
        and left.source_position == right.source_position
        and left.spell_id == right.spell_id
        and type(left.area_geometry) is type(right.area_geometry)
        and left.area_geometry == right.area_geometry
    )


def _merge_spell_root_presentation_authority(
    existing: _SpellRootPresentationAuthority,
    candidate: _SpellRootPresentationAuthority,
) -> _SpellRootPresentationAuthority:
    if not _spell_root_authority_signature_matches(existing, candidate):
        raise SubjectiveEventProjectionError(
            "spell root presentation authority changed across lifecycle"
        )
    return _SpellRootPresentationAuthority(
        runtime_type=existing.runtime_type,
        lineage_uuid=existing.lineage_uuid,
        source_entity_uuid=existing.source_entity_uuid,
        source_position=existing.source_position,
        spell_id=existing.spell_id,
        area_geometry=existing.area_geometry,
        identified_source_observer_uuids=(
            existing.identified_source_observer_uuids
            | candidate.identified_source_observer_uuids
        ),
        located_source_observer_uuids=(
            existing.located_source_observer_uuids
            | candidate.located_source_observer_uuids
        ),
    )


def _spell_root_authority_matches_event(
    authority: _SpellRootPresentationAuthority,
    event: SpellEvent,
) -> bool:
    try:
        source_position = (
            None
            if event.source_position is None
            else _require_position(
                event.source_position,
                field_name="spell root source_position",
            )
        )
    except SubjectiveEventProjectionError:
        return False
    return (
        type(event) is authority.runtime_type
        and type(event.lineage_uuid) is UUID
        and event.lineage_uuid == authority.lineage_uuid
        and type(event.source_entity_uuid) is UUID
        and event.source_entity_uuid == authority.source_entity_uuid
        and event.event_type is EventType.CAST_SPELL
        and event.phase is EventPhase.COMPLETION
        and event.canceled is False
        and event.canceled_from_phase is None
        and event.application_index is None
        and type(event.spell_id) is str
        and event.spell_id == authority.spell_id
        and source_position == authority.source_position
        and type(event.area_geometry) is type(authority.area_geometry)
        and event.area_geometry == authority.area_geometry
    )


class _BatchIndex:
    """In-batch lineage topology; it never consults EventQueue or registries."""

    def __init__(self, batch: CausalEventBatch, *, generation_id: str) -> None:
        self.slots = batch.slots
        self.completions = tuple(
            slot
            for slot in batch.slots
            if slot.event.phase is EventPhase.COMPLETION and not slot.event.canceled
        )
        self.completion_by_lineage: dict[str, ProjectedEventSlot] = {}
        self.first_cursor_by_lineage: dict[str, int] = {}
        event_lineage_by_uuid: dict[UUID, str] = {}
        self.slot_by_event_uuid: dict[UUID, ProjectedEventSlot] = {}
        self.movement_root_by_effect_uuid: dict[
            UUID,
            MovementRootProjectionContext,
        ] = {}
        self.movement_root_by_lineage: dict[
            UUID,
            MovementRootProjectionContext,
        ] = {}
        self.spell_root_authority_by_lineage: dict[
            UUID,
            _SpellRootPresentationAuthority,
        ] = {}
        self.spell_root_lifecycle_lineages: set[UUID] = set()
        invalid_spell_root_lineages: set[UUID] = set()
        for view in batch.movement_root_contexts:
            context = view.context
            if context.generation_id != generation_id:
                raise SubjectiveEventProjectionError(
                    "movement root context belongs to another generation"
                )
            if context.lineage_uuid in self.movement_root_by_lineage:
                raise SubjectiveEventProjectionError(
                    "movement root lineage has ambiguous context ownership"
                )
            self.movement_root_by_lineage[context.lineage_uuid] = context
            for alias in view.effect_uuid_aliases:
                if alias.effect_uuid in self.movement_root_by_effect_uuid:
                    raise SubjectiveEventProjectionError(
                        "movement root EFFECT alias has ambiguous ownership"
                    )
                self.movement_root_by_effect_uuid[alias.effect_uuid] = context
        for slot in batch.slots:
            event = slot.event
            if (
                isinstance(event, SpellEvent)
                and event.application_index is None
                and event.phase in {
                    EventPhase.DECLARATION,
                    EventPhase.EXECUTION,
                    EventPhase.EFFECT,
                    EventPhase.COMPLETION,
                }
            ):
                lineage_uuid = event.lineage_uuid
                self.spell_root_lifecycle_lineages.add(lineage_uuid)
                try:
                    candidate = _capture_spell_root_presentation_authority(event)
                    existing = self.spell_root_authority_by_lineage.get(lineage_uuid)
                    if existing is None:
                        self.spell_root_authority_by_lineage[lineage_uuid] = candidate
                    else:
                        self.spell_root_authority_by_lineage[lineage_uuid] = (
                            _merge_spell_root_presentation_authority(
                                existing,
                                candidate,
                            )
                        )
                except (TypeError, ValueError, SubjectiveEventProjectionError):
                    invalid_spell_root_lineages.add(lineage_uuid)

            lineage = str(slot.event.lineage_uuid)
            event_lineage_by_uuid[slot.event.uuid] = lineage
            self.slot_by_event_uuid[slot.event.uuid] = slot
            self.first_cursor_by_lineage.setdefault(lineage, slot.source_event_cursor)
            if slot.event.phase is EventPhase.COMPLETION and not slot.event.canceled:
                self.completion_by_lineage[lineage] = slot

        for lineage_uuid in invalid_spell_root_lineages:
            self.spell_root_authority_by_lineage.pop(lineage_uuid, None)

        self.parent_by_lineage: dict[str, str] = {}
        for slot in batch.slots:
            event = slot.event
            lineage = str(event.lineage_uuid)
            parent = (
                str(event.parent_lineage)
                if event.parent_lineage is not None
                else event_lineage_by_uuid.get(event.parent_event)
                if event.parent_event is not None
                else None
            )
            if parent is not None and parent != lineage:
                self.parent_by_lineage[lineage] = parent

    def ancestors(self, lineage: str, *, include_self: bool = False) -> tuple[str, ...]:
        """Return nearest-first ancestors, stopping safely on malformed cycles."""
        result: list[str] = [lineage] if include_self else []
        seen = {lineage}
        current = lineage
        while current in self.parent_by_lineage:
            current = self.parent_by_lineage[current]
            if current in seen:
                break
            result.append(current)
            seen.add(current)
        return tuple(result)

    def root_order_cursor(self, lineage: str, fallback: int) -> int:
        """Return the earliest exact cursor in this causal ancestry."""
        cursors = [
            self.first_cursor_by_lineage[ancestor]
            for ancestor in self.ancestors(lineage, include_self=True)
            if ancestor in self.first_cursor_by_lineage
        ]
        return min(cursors, default=fallback)

    def movement_root_for_step(
        self,
        step: StepMovementEvent,
    ) -> MovementRootProjectionContext:
        """Resolve only the exact root EFFECT UUID carried by Step.parent_event."""
        if type(step.parent_event) is not UUID:
            raise SubjectiveEventProjectionError(
                "movement Step requires an exact parent_event EFFECT alias"
            )
        context = self.movement_root_by_effect_uuid.get(step.parent_event)
        if context is None:
            raise SubjectiveEventProjectionError(
                "movement Step parent_event does not resolve to a frozen root EFFECT"
            )
        return context

    def spell_source_identity_allowed(
        self,
        event: SpellEvent,
        perspective: SubjectivePerspective,
    ) -> bool:
        """Use the union of grants proven by this exact spell-root lifecycle."""
        authority = self._spell_root_authority(event)
        if authority is None:
            return (
                False
                if event.lineage_uuid in self.spell_root_lifecycle_lineages
                else _identity_allowed(event, event.source_entity_uuid, perspective)
            )
        source_key = str(event.source_entity_uuid)
        if source_key in perspective.controlled_entity_uuids:
            return True
        return bool(
            set(perspective.observer_entity_uuids)
            & authority.identified_source_observer_uuids
        )

    def spell_source_location_allowed(
        self,
        event: SpellEvent,
        perspective: SubjectivePerspective,
    ) -> bool:
        """Authorize declared spell geometry from the same frozen root boundary."""
        authority = self._spell_root_authority(event)
        if authority is None:
            return (
                False
                if event.lineage_uuid in self.spell_root_lifecycle_lineages
                else _location_allowed(event, event.source_entity_uuid, perspective)
            )
        source_key = str(event.source_entity_uuid)
        if source_key in perspective.controlled_entity_uuids:
            return True
        return bool(
            set(perspective.observer_entity_uuids)
            & authority.located_source_observer_uuids
        )

    def _spell_root_authority(
        self,
        event: SpellEvent,
    ) -> _SpellRootPresentationAuthority | None:
        authority = self.spell_root_authority_by_lineage.get(event.lineage_uuid)
        if authority is None or not _spell_root_authority_matches_event(
            authority,
            event,
        ):
            return None
        return authority


class CanonicalSubjectivePresentationMapper:
    """Journal projector for exact engine batches and canonical subjective cues."""

    def project_frame(
        self,
        source: CausalEventBatch,
        context: SubjectiveFrameProjectionContext,
    ) -> SubjectiveReplicationFrame:
        """Project one exact source interval into a closed subjective frame."""
        previous = context.previous_watermarks
        if context.next_observation_cursor != previous.observation_cursor + 1:
            raise SubjectiveEventProjectionError(
                "observation cursor must advance by exactly one"
            )
        if source.through_source_event_cursor < previous.source_event_cursor:
            raise SubjectiveEventProjectionError("source event watermark moved backwards")
        if source.slots:
            expected_first = previous.source_event_cursor + 1
            if source.slots[0].source_event_cursor != expected_first:
                raise SubjectiveEventProjectionError(
                    "source batch must begin immediately after the prior watermark"
                )
        elif source.through_source_event_cursor != previous.source_event_cursor:
            raise SubjectiveEventProjectionError(
                "an advancing source watermark requires its exact event slots"
            )

        index = _BatchIndex(
            source,
            generation_id=context.protocol.generation_id,
        )
        nodes = _build_semantic_nodes(
            source,
            index=index,
            perspective=context.perspective,
        )
        drafts = tuple(
            PresentationNodeDraft(
                key=node.key,
                parent_key=node.parent_key,
                order_key=node.order_key,
                factory=lambda coordinates, node=node: _materialize_node(
                    node,
                    coordinates,
                ),
            )
            for node in nodes
        )
        cues = materialize_presentation_graph(
            drafts,
            perspective_epoch_id=context.perspective.perspective_epoch_id,
            observation_cursor=context.next_observation_cursor,
            presentation_from_cursor=previous.presentation_cursor,
        )
        watermarks = PlayerReplicationWatermarks(
            source_event_cursor=source.through_source_event_cursor,
            observation_cursor=context.next_observation_cursor,
            presentation_cursor=previous.presentation_cursor + len(cues),
            combat_log_cursor=previous.combat_log_cursor,
        )
        return SubjectiveReplicationFrame(
            source_stream_id=context.protocol.source_stream_id,
            generation_id=context.protocol.generation_id,
            perspective_epoch_id=context.perspective.perspective_epoch_id,
            watermarks=watermarks,
            presentation_from_cursor=previous.presentation_cursor,
            patches=source.patches,
            presentation=cues,
        )


def _build_semantic_nodes(
    batch: CausalEventBatch,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> tuple[_NodeSpec, ...]:
    nodes: list[_NodeSpec] = []
    nodes_by_key: dict[str, _NodeSpec] = {}
    semantic_key_by_lineage: dict[str, str] = {}
    spell_application_by_lineage: dict[str, tuple[str, _SpellApplication]] = {}
    latest_sensory_cursor_by_observer = {
        str(slot.event.observer_uuid): slot.source_event_cursor
        for slot in index.completions
        if isinstance(slot.event, SensoryUpdateEvent)
    }

    def add(node: _NodeSpec, *, map_lineage: bool = True) -> None:
        if node.key in nodes_by_key:
            raise SubjectiveEventProjectionError(
                f"duplicate semantic node key: {node.key}"
            )
        nodes.append(node)
        nodes_by_key[node.key] = node
        if map_lineage:
            semantic_key_by_lineage[node.lineage] = node.key

    for slot in index.completions:
        event = slot.event
        node: Optional[_NodeSpec] = None
        if isinstance(
            event,
            (
                MovementEvent,
                JumpEvent,
                TraverseConnectorEvent,
                StepMovementEvent,
            ),
        ):
            continue
        if isinstance(event, ShoveEvent):
            node = _shove_node(slot, index=index, perspective=perspective)
        elif isinstance(event, CounterspellReactionEvent):
            node = _counterspell_node(
                slot,
                index=index,
                perspective=perspective,
            )
        elif isinstance(event, AttackEvent):
            node = _attack_node(slot, index=index, perspective=perspective)
        elif isinstance(event, SpellEvent):
            if event.application_index is not None:
                continue
            spell_result = _spell_node(slot, index=index, perspective=perspective)
            if spell_result is not None:
                node, applications = spell_result
                for application in applications:
                    spell_application_by_lineage[application.source_lineage] = (
                        node.key,
                        application,
                    )
        elif (
            isinstance(event, ActionEvent)
            and event.presentation_kind is ActionPresentationKind.DRINK
        ):
            node = _item_node(slot, index=index, perspective=perspective)
        elif isinstance(event, ActionEvent):
            node = _action_node(slot, index=index, perspective=perspective)
        elif isinstance(event, DamageAppliedEvent):
            node = _damage_node(slot, index=index, perspective=perspective)
        elif isinstance(event, ForcedMovementEvent):
            node = _forced_node(slot, index=index, perspective=perspective)
        elif isinstance(event, HealEvent):
            node = _heal_node(slot, index=index, perspective=perspective)
        elif isinstance(event, (ReviveEvent, InstantDeathEvent, DeathSaveEvent)):
            node = _lifecycle_cause_node(slot, index=index, perspective=perspective)
        elif isinstance(event, LifeStateChangeEvent):
            node = _life_node(slot, index=index, perspective=perspective)
        elif isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)):
            node = _condition_node(slot, index=index, perspective=perspective)
        elif isinstance(event, SensoryUpdateEvent):
            if (
                latest_sensory_cursor_by_observer.get(str(event.observer_uuid))
                == slot.source_event_cursor
            ):
                node = _light_node(slot, index=index, perspective=perspective)
        elif isinstance(event, SpatialEffectChangeEvent):
            node = _spatial_effect_node(
                slot,
                index=index,
                perspective=perspective,
            )
        elif isinstance(
            event,
            (
                EncounterStartEvent,
                EncounterEndEvent,
                RoundStartEvent,
                RoundEndEvent,
                TurnStartEvent,
                TurnEndEvent,
            ),
        ):
            node = _encounter_node(slot, index=index, perspective=perspective)
        if node is not None:
            add(node)

    _add_patch_backed_nodes(
        batch,
        index=index,
        perspective=perspective,
        add=add,
    )
    handler_parent_by_lineage = _add_effective_handler_nodes(
        batch,
        index=index,
        perspective=perspective,
        nodes=nodes,
        add=add,
    )

    _attach_semantic_nodes(
        nodes=nodes,
        nodes_by_key=nodes_by_key,
        semantic_key_by_lineage=semantic_key_by_lineage,
        spell_application_by_lineage=spell_application_by_lineage,
        index=index,
        perspective=perspective,
        handler_parent_by_lineage=handler_parent_by_lineage,
        add=add,
    )
    reactive_step_lineage_by_node_key = _pre_edge_reactive_step_lineages(
        nodes,
        index=index,
    )
    arrival_step_lineage_by_node_key = _post_arrival_damage_step_lineages(
        nodes,
        index=index,
    )
    _add_movement_nodes(
        index=index,
        perspective=perspective,
        add=add,
        semantic_key_by_lineage=semantic_key_by_lineage,
        reactive_step_lineages=frozenset(
            reactive_step_lineage_by_node_key.values()
        ),
        post_arrival_step_lineages=frozenset(
            arrival_step_lineage_by_node_key.values()
        ),
    )
    _attach_movement_reactions(
        nodes=nodes,
        nodes_by_key=nodes_by_key,
        semantic_key_by_lineage=semantic_key_by_lineage,
        reactive_step_lineage_by_node_key=reactive_step_lineage_by_node_key,
    )
    _order_post_arrival_damage(
        nodes_by_key=nodes_by_key,
        semantic_key_by_lineage=semantic_key_by_lineage,
        arrival_step_lineage_by_node_key=arrival_step_lineage_by_node_key,
    )
    return tuple(nodes)


def _pre_edge_reactive_step_lineages(
    nodes: list[_NodeSpec],
    *,
    index: _BatchIndex,
) -> dict[str, str]:
    """Map surviving pre-edge reactions to their exact committed steps.

    This runs after nonmovement semantic validation. Hidden or invalid actions
    therefore cannot leak through an otherwise unexplained movement split. A
    reaction must also commit before its exact step; later descendants remain
    independent root cues instead of being assigned false pre-motion timing.
    """
    step_lineage_by_node_key: dict[str, str] = {}
    for node in nodes:
        if (
            node.kind not in {
                _NodeKind.ATTACK,
                _NodeKind.SPELL,
                _NodeKind.SHOVE,
            }
            or node.parent_key is not None
        ):
            continue
        step_lineage = _nearest_completed_step_lineage(node, index=index)
        step_slot = (
            index.completion_by_lineage.get(step_lineage)
            if step_lineage is not None
            else None
        )
        if (
            step_lineage is not None
            and step_slot is not None
            and node.slot.source_event_cursor < step_slot.source_event_cursor
        ):
            step_lineage_by_node_key[node.key] = step_lineage
    return step_lineage_by_node_key


def _nearest_completed_step_lineage(
    node: _NodeSpec,
    *,
    index: _BatchIndex,
) -> Optional[str]:
    """Return the exact completed movement step that causally owns ``node``."""
    for ancestor in index.ancestors(node.lineage):
        slot = index.completion_by_lineage.get(ancestor)
        if (
            slot is not None
            and isinstance(slot.event, StepMovementEvent)
        ):
            return ancestor
    return None


def _post_arrival_damage_step_lineages(
    nodes: list[_NodeSpec],
    *,
    index: _BatchIndex,
) -> dict[str, str]:
    """Authenticate damage caused by entering one committed destination cell."""
    step_lineage_by_node_key: dict[str, str] = {}
    for node in nodes:
        if node.kind is not _NodeKind.DAMAGE or node.parent_key is not None:
            continue
        payload = node.payload
        if not isinstance(payload, _DamagePayload):
            continue
        ancestors = index.ancestors(node.lineage)
        for ancestor_index, ancestor in enumerate(ancestors):
            entered_slot = index.completion_by_lineage.get(ancestor)
            entered = entered_slot.event if entered_slot is not None else None
            if (
                not isinstance(entered, SpatialChangeEvent)
                or entered.change_type is not SpatialChangeType.ENTITY_ENTERED
                or entered.entity_uuid is None
                or str(entered.entity_uuid) != payload.target_uuid
            ):
                continue
            for step_ancestor in ancestors[ancestor_index + 1:]:
                step_slot = index.completion_by_lineage.get(step_ancestor)
                step = step_slot.event if step_slot is not None else None
                if (
                    isinstance(step, StepMovementEvent)
                    and step.committed
                    and step.source_entity_uuid == entered.entity_uuid
                    and step.to_position == entered.position
                ):
                    step_lineage_by_node_key[node.key] = step_ancestor
                    break
            break
    return step_lineage_by_node_key


def _add_movement_nodes(
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
    add: object,
    semantic_key_by_lineage: dict[str, str],
    reactive_step_lineages: frozenset[str],
    post_arrival_step_lineages: frozenset[str],
) -> None:
    """Validate exact root-owned Steps, then project authorized local runs.

    Movement-owned Attack, Spell, and Shove cues are pre-edge reactions. The
    owning segment therefore begins with the exact triggering step; later
    nonreactive steps may remain coalesced until the next reaction boundary.
    """
    grouped: dict[
        UUID,
        list[tuple[ProjectedEventSlot, MovementRootProjectionContext]],
    ] = {}
    seen_path_indexes: dict[UUID, set[int]] = {}
    for slot in index.completions:
        if not isinstance(slot.event, StepMovementEvent):
            continue
        step = slot.event
        context = index.movement_root_for_step(step)
        validate_step_against_movement_root(step, context)
        path_indexes = seen_path_indexes.setdefault(context.lineage_uuid, set())
        if step.path_index in path_indexes:
            raise SubjectiveEventProjectionError(
                "movement root contains duplicate Step path indexes"
            )
        path_indexes.add(step.path_index)
        grouped.setdefault(context.lineage_uuid, []).append((slot, context))

    add_node = add
    if not callable(add_node):
        raise TypeError("movement node sink must be callable")
    for root_lineage_uuid, candidates in grouped.items():
        contexts = {id(context): context for _, context in candidates}
        if len(contexts) != 1:
            raise SubjectiveEventProjectionError(
                "movement root lineage resolved to more than one frozen context"
            )
        context = next(iter(contexts.values()))
        if type(context) in {JumpRootContext, ConnectorRootContext} and len(candidates) != 1:
            raise SubjectiveEventProjectionError(
                "one-leg locomotion root contains multiple completed Steps"
            )
        candidates.sort(key=lambda candidate: _movement_step_slot_order(candidate[0]))
        authorized: list[ProjectedEventSlot] = []
        for slot, _ in candidates:
            step = slot.event
            if not isinstance(step, StepMovementEvent):
                continue
            step_lineage = str(step.lineage_uuid)
            if not step.committed and step_lineage not in reactive_step_lineages:
                continue
            if not _movement_root_identity_allowed(context, perspective):
                continue
            if not _step_geometry_allowed(step, perspective):
                continue
            authorized.append(slot)

        segments: list[list[ProjectedEventSlot]] = []
        for slot in authorized:
            step = slot.event
            if not isinstance(step, StepMovementEvent):
                continue
            if type(context) is not PathMovementRootContext or not step.committed:
                segments.append([slot])
                continue
            if not segments:
                segments.append([slot])
                continue
            previous_slot = segments[-1][-1]
            previous = previous_slot.event
            if not isinstance(previous, StepMovementEvent) or not previous.committed:
                segments.append([slot])
                continue
            contiguous = (
                step.path_index == previous.path_index + 1
                and step.from_position == previous.to_position
                and step.from_elevation_feet == previous.to_elevation_feet
                and str(step.lineage_uuid) not in reactive_step_lineages
                and str(previous.lineage_uuid) not in post_arrival_step_lineages
            )
            if contiguous:
                segments[-1].append(slot)
            else:
                segments.append([slot])

        root_lineage = str(root_lineage_uuid)
        for segment_index, segment in enumerate(segments):
            first = segment[0].event
            last_slot = segment[-1]
            if not isinstance(first, StepMovementEvent):
                continue
            key = f"movement:{last_slot.event.uuid}:{segment_index}"
            node = _NodeSpec(
                key=key,
                kind=_NodeKind.MOVEMENT,
                slot=last_slot,
                payload=_MovementPayload(
                    entity_uuid=str(first.source_entity_uuid),
                    locomotion_family=_locomotion_family(context),
                    trajectory_family=_locomotion_trajectory(context),
                    anchors=_locomotion_anchors(segment),
                    connector=_connector_presentation_identity(context),
                    endpoint_outcome=(
                        MovementEndpointOutcome.COMMITTED
                        if first.committed
                        else MovementEndpointOutcome.NOT_COMMITTED
                    ),
                ),
                lineage=root_lineage,
                order_key=(
                    context.first_effect_source_cursor,
                    10,
                    first.path_index,
                    segment_index,
                ),
            )
            add_node(node, map_lineage=False)
            for step_slot in segment:
                semantic_key_by_lineage[str(step_slot.event.lineage_uuid)] = key
            semantic_key_by_lineage.setdefault(root_lineage, key)


def _movement_step_slot_order(
    slot: ProjectedEventSlot,
) -> tuple[int, int]:
    step = slot.event
    if type(step) is not StepMovementEvent:
        raise SubjectiveEventProjectionError("movement candidate is not an exact Step")
    return step.path_index, slot.source_event_cursor


def validate_step_against_movement_root(
    step: StepMovementEvent,
    context: MovementRootProjectionContext,
) -> None:
    """Fail before privacy filtering when one Step contradicts frozen authority."""
    if (
        type(step) is not StepMovementEvent
        or step.phase is not EventPhase.COMPLETION
        or type(step.canceled) is not bool
        or step.canceled
        or step.canceled_from_phase is not None
        or type(step.event_type) is not EventType
        or step.event_type is not EventType.STEP_MOVEMENT
        or type(step.uuid) is not UUID
        or type(step.lineage_uuid) is not UUID
        or type(step.source_entity_uuid) is not UUID
        or step.source_entity_uuid != context.source_entity_uuid
        or type(step.parent_event) is not UUID
        or type(step.parent_lineage) is not UUID
        or step.parent_lineage != context.lineage_uuid
        or type(step.path_index) is not int
        or step.path_index < 1
        or type(step.total_path_length) is not int
        or step.total_path_length < 2
        or type(step.trajectory) is not MovementTrajectory
        or type(step.committed) is not bool
    ):
        raise SubjectiveEventProjectionError(
            "movement Step changed root, lifecycle, or typed path evidence"
        )
    from_position = _require_position(step.from_position, field_name="Step origin")
    to_position = _require_position(step.to_position, field_name="Step destination")
    from_elevation = _require_elevation(
        step.from_elevation_feet,
        field_name="Step origin elevation",
    )
    to_elevation = _require_elevation(
        step.to_elevation_feet,
        field_name="Step destination elevation",
    )
    disclosed_path = _require_position_path(
        step.disclosed_path,
        field_name="Step disclosed path",
        minimum_length=2,
    )
    if type(context) is PathMovementRootContext:
        if (
            step.trajectory is not MovementTrajectory.PATH
            or step.total_path_length != len(context.admitted_path)
            or step.path_index >= len(context.admitted_path)
            or from_position != context.admitted_path[step.path_index - 1]
            or to_position != context.admitted_path[step.path_index]
            or disclosed_path != (from_position, to_position)
        ):
            raise SubjectiveEventProjectionError(
                "PATH Step contradicts the admitted root path"
            )
        return
    if type(context) is JumpRootContext:
        if (
            step.trajectory is not MovementTrajectory.DIRECT_ARC
            or step.path_index != 1
            or step.total_path_length != len(context.disclosed_arc)
            or disclosed_path != context.disclosed_arc
            or from_position != context.takeoff_position
            or to_position != context.landing_position
            or from_elevation != context.takeoff_elevation_feet
            or to_elevation != context.landing_elevation_feet
        ):
            raise SubjectiveEventProjectionError(
                "DIRECT_ARC Step contradicts the frozen Jump root"
            )
        return
    if type(context) is ConnectorRootContext:
        if (
            step.trajectory is not MovementTrajectory.CONNECTOR_TRANSFER
            or step.path_index != 1
            or step.total_path_length != 2
            or disclosed_path != (context.source_position, context.destination_position)
            or from_position != context.source_position
            or to_position != context.destination_position
            or from_elevation != context.source_elevation_feet
            or to_elevation != context.destination_elevation_feet
        ):
            raise SubjectiveEventProjectionError(
                "CONNECTOR_TRANSFER Step contradicts the frozen connector root"
            )
        return
    raise SubjectiveEventProjectionError("unsupported frozen movement root context")


def _movement_root_identity_allowed(
    context: MovementRootProjectionContext,
    perspective: SubjectivePerspective,
) -> bool:
    source = str(context.source_entity_uuid)
    if source in perspective.controlled_entity_uuids:
        return True
    return bool(
        context.identified_source_observer_uuids
        & frozenset(perspective.observer_entity_uuids)
    )


def _locomotion_family(
    context: MovementRootProjectionContext,
) -> LocomotionFamily:
    if type(context) is JumpRootContext:
        return LocomotionFamily.JUMP
    if type(context) is ConnectorRootContext:
        return LocomotionFamily.CONNECTOR
    if type(context) is not PathMovementRootContext:
        raise SubjectiveEventProjectionError("unsupported movement root family")
    match context.movement_mode:
        case MovementMode.WALKING:
            return LocomotionFamily.WALK
        case MovementMode.SWIMMING:
            return LocomotionFamily.SWIM
        case MovementMode.FLYING:
            return LocomotionFamily.FLY
        case MovementMode.BURROWING:
            return LocomotionFamily.BURROW
    raise SubjectiveEventProjectionError("unhandled path movement mode")


def _locomotion_trajectory(
    context: MovementRootProjectionContext,
) -> LocomotionTrajectory:
    if type(context) is PathMovementRootContext:
        return LocomotionTrajectory.PATH
    if type(context) is JumpRootContext:
        return LocomotionTrajectory.DIRECT_ARC
    if type(context) is ConnectorRootContext:
        return LocomotionTrajectory.CONNECTOR_TRANSFER
    raise SubjectiveEventProjectionError("unsupported movement root trajectory")


def _locomotion_anchors(
    segment: list[ProjectedEventSlot],
) -> tuple[LocomotionAnchor, ...]:
    first = segment[0].event
    if not isinstance(first, StepMovementEvent):
        raise SubjectiveEventProjectionError("locomotion segment has no Step")
    return (
        LocomotionAnchor(
            position=first.from_position,
            elevation_feet=first.from_elevation_feet,
        ),
        *tuple(
            LocomotionAnchor(
                position=step_slot.event.to_position,
                elevation_feet=step_slot.event.to_elevation_feet,
            )
            for step_slot in segment
            if isinstance(step_slot.event, StepMovementEvent)
        ),
    )


def _connector_presentation_identity(
    context: MovementRootProjectionContext,
) -> Optional[ConnectorPresentationIdentity]:
    if type(context) is not ConnectorRootContext:
        return None
    return ConnectorPresentationIdentity(
        uuid=context.connector_uuid,
        authored_id=context.connector_authored_id,
        kind=context.connector_kind,
        presentation_key=context.connector_presentation_key,
        revision=context.connector_revision,
    )


def _attach_movement_reactions(
    *,
    nodes: list[_NodeSpec],
    nodes_by_key: dict[str, _NodeSpec],
    semantic_key_by_lineage: dict[str, str],
    reactive_step_lineage_by_node_key: dict[str, str],
) -> None:
    """Attach surviving pre-edge reactions to their exact movement segment."""
    for node in nodes:
        if node.parent_key is not None:
            continue
        step_lineage = reactive_step_lineage_by_node_key.get(node.key)
        parent_key = (
            semantic_key_by_lineage.get(step_lineage)
            if step_lineage is not None
            else None
        )
        parent = nodes_by_key.get(parent_key) if parent_key is not None else None
        if parent is not None and parent.kind is _NodeKind.MOVEMENT:
            node.parent_key = parent.key


def _order_post_arrival_damage(
    *,
    nodes_by_key: dict[str, _NodeSpec],
    semantic_key_by_lineage: dict[str, str],
    arrival_step_lineage_by_node_key: dict[str, str],
) -> None:
    """Schedule authenticated entry damage after its exact visible arrival."""
    for node_key, step_lineage in arrival_step_lineage_by_node_key.items():
        damage = nodes_by_key.get(node_key)
        movement_key = semantic_key_by_lineage.get(step_lineage)
        movement = (
            nodes_by_key.get(movement_key)
            if movement_key is not None
            else None
        )
        if (
            damage is None
            or damage.parent_key is not None
            or not isinstance(damage.payload, _DamagePayload)
            or movement is None
            or not isinstance(movement.payload, _MovementPayload)
            or damage.payload.target_uuid != movement.payload.entity_uuid
        ):
            continue
        damage.order_key = (
            *movement.order_key,
            90,
            damage.slot.source_event_cursor,
        )


def _attack_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, AttackEvent) or event.target_entity_uuid is None:
        return None
    if event.attack_outcome is None:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    outcome = _attack_outcome(event.attack_outcome)
    if outcome is None:
        return None
    damage_types = tuple(
        dict.fromkeys(PresentationDamageType(value.value) for value in event.damage_types)
    )
    if not damage_types:
        return None
    weapon_slot = _weapon_slot(event.weapon_slot)
    ranged = event.weapon_slot in {WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF}
    lineage = str(event.lineage_uuid)
    attributions = (
        *_behavior_content_attributions(event.behavior_binding),
        *_source_item_content_attributions(event),
    )
    return _NodeSpec(
        key=f"attack:{event.uuid}",
        kind=_NodeKind.ATTACK,
        slot=slot,
        payload=_AttackPayload(
            actor_uuid=str(event.source_entity_uuid),
            target_uuid=str(event.target_entity_uuid),
            action_name=event.name or event.weapon_name or "Attack",
            outcome=outcome,
            delivery=AttackDelivery.PROJECTILE if ranged else AttackDelivery.MELEE,
            weapon_slot=weapon_slot,
            damage_types=damage_types,
            projectile_type=PresentationProjectile.BOLT if ranged else None,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 20, slot.source_event_cursor),
        content_attributions=attributions,
    )


def _counterspell_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    """Project one fully attributed Counterspell reaction or fail closed."""
    event = slot.event
    if not isinstance(event, CounterspellReactionEvent):
        return None
    if event.target_entity_uuid is None:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None

    incoming_slot = index.slot_by_event_uuid.get(event.triggered_event_uuid)
    if incoming_slot is None or not isinstance(incoming_slot.event, SpellEvent):
        return None
    incoming = incoming_slot.event
    if incoming.lineage_uuid != event.triggered_lineage_uuid:
        return None
    if incoming.source_entity_uuid != event.target_entity_uuid:
        return None

    behavior = _behavior_content_attributions(
        event.behavior_binding,
        role=BehaviorPresentationRole.BEHAVIOR,
    )
    trigger = _behavior_content_attributions(
        incoming.behavior_binding,
        role=BehaviorPresentationRole.TRIGGER_BEHAVIOR,
    )
    if len(behavior) != 1 or len(trigger) != 1:
        return None

    incoming_level = event.incoming_spell_level
    if event.automatic:
        if (
            not event.succeeded
            or event.check_total is not None
            or event.check_dc is not None
            or event.counterspell_slot_level < incoming_level
        ):
            return None
        resolution: CounterspellResolution = CounterspellAutomaticSuccess()
    else:
        if (
            event.check_total is None
            or event.check_dc is None
            or event.check_dc != 10 + incoming_level
            or event.counterspell_slot_level >= incoming_level
        ):
            return None
        if event.succeeded:
            if event.check_total < event.check_dc:
                return None
            resolution = CounterspellCheckSuccess(
                check_total=event.check_total,
                check_dc=event.check_dc,
            )
        else:
            if event.check_total >= event.check_dc:
                return None
            resolution = CounterspellCheckFailure(
                check_total=event.check_total,
                check_dc=event.check_dc,
            )

    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"counterspell:{event.uuid}",
        kind=_NodeKind.COUNTERSPELL,
        slot=slot,
        payload=_CounterspellPayload(
            reactor_uuid=str(event.source_entity_uuid),
            incoming_caster_uuid=str(event.target_entity_uuid),
            incoming_spell_level=incoming_level,
            counterspell_slot_level=event.counterspell_slot_level,
            resolution=resolution,
        ),
        lineage=lineage,
        order_key=(
            index.root_order_cursor(lineage, slot.source_event_cursor),
            20,
            slot.source_event_cursor,
        ),
        content_attributions=behavior + trigger,
    )


def _spell_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[tuple[_NodeSpec, list[_SpellApplication]]]:
    event = slot.event
    if not isinstance(event, SpellEvent):
        return None
    if not index.spell_source_identity_allowed(event, perspective):
        return None
    if not event.spell_id:
        return None
    try:
        school = PresentationSpellSchool(event.spell_school.strip().lower())
    except ValueError:
        return None
    projectile = _projectile(event.projectile_type)
    if event.projectile_type is not None and projectile is None:
        return None
    area = _area_geometry(event)
    if event.area_geometry is not None and area is None:
        return None
    if area is not None and not index.spell_source_location_allowed(
        event,
        perspective,
    ):
        return None

    lineage = str(event.lineage_uuid)
    application_slots = [
        candidate
        for candidate in index.completions
        if isinstance(candidate.event, SpellEvent)
        and candidate.event.application_index is not None
        and lineage in index.ancestors(str(candidate.event.lineage_uuid))
    ]
    application_slots.sort(
        key=lambda candidate: (
            candidate.event.application_index
            if isinstance(candidate.event, SpellEvent)
            and candidate.event.application_index is not None
            else 0,
            candidate.source_event_cursor,
        )
    )
    applications: list[_SpellApplication] = []
    for application_slot in application_slots:
        application_event = application_slot.event
        if not isinstance(application_event, SpellEvent):
            continue
        target_uuid = application_event.target_entity_uuid
        if target_uuid is None or not _identity_allowed(
            application_event,
            target_uuid,
            perspective,
        ):
            continue
        applications.append(
            _SpellApplication(
                source_lineage=str(application_event.lineage_uuid),
                outcome=_spell_application_outcome(application_event),
                target_uuid=str(target_uuid),
                position=None,
            )
        )

    if not application_slots and event.target_entity_uuid is not None:
        if _identity_allowed(event, event.target_entity_uuid, perspective):
            applications.append(
                _SpellApplication(
                    source_lineage=lineage,
                    outcome=_spell_application_outcome(event),
                    target_uuid=str(event.target_entity_uuid),
                    position=None,
                )
            )

    if area is not None:
        delivery = SpellDelivery.AOE
    elif event.range_type is not None and event.range_type.strip().lower() == "self":
        delivery = SpellDelivery.SELF
    elif event.range_type is not None and event.range_type.strip().lower() == "touch":
        delivery = SpellDelivery.TOUCH
    elif projectile is not None:
        delivery = (
            SpellDelivery.MISSILE_VOLLEY
            if len(applications) > 1
            else SpellDelivery.PROJECTILE
        )
    else:
        delivery = SpellDelivery.DIRECT

    payload = _SpellPayload(
        actor_uuid=str(event.source_entity_uuid),
        spell_id=event.spell_id,
        spell_name=event.name or event.spell_id or "Spell",
        spell_school=school,
        spell_level=event.cast_at_level if event.cast_at_level > 0 else event.spell_level,
        delivery=delivery,
        projectile_type=projectile,
        area=area,
        applications=applications,
    )
    node = _NodeSpec(
        key=f"spell:{event.uuid}",
        kind=_NodeKind.SPELL,
        slot=slot,
        payload=payload,
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 20, slot.source_event_cursor),
        content_attributions=_behavior_content_attributions(
            event.behavior_binding,
        ),
    )
    return node, applications


def _item_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, ActionEvent):
        return None
    snapshot = event.source_item_presentation
    if snapshot is None or event.source_item_uuid is None:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    lineage = str(event.lineage_uuid)
    attributions = (
        *_behavior_content_attributions(event.behavior_binding),
        *_source_item_content_attributions(event),
    )
    return _NodeSpec(
        key=f"item:{event.uuid}",
        kind=_NodeKind.ITEM,
        slot=slot,
        payload=_ItemPayload(
            actor_uuid=str(event.source_entity_uuid),
            item_uuid=str(snapshot.item_uuid),
            item_kind=snapshot.item_kind,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 20, slot.source_event_cursor),
        content_attributions=attributions,
    )


def _shove_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, ShoveEvent) or event.target_entity_uuid is None:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    outcome = (
        ShoveOutcome.RESISTED
        if event.contest_success is False
        else ShoveOutcome.SUCCEEDED_PRONE
        if event.knocked_prone
        else ShoveOutcome.SUCCEEDED_PUSH
        if event.push_distance > 0
        else ShoveOutcome.SUCCEEDED_BLOCKED
    )
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"shove:{event.uuid}",
        kind=_NodeKind.SHOVE,
        slot=slot,
        payload=_ShovePayload(
            actor_uuid=str(event.source_entity_uuid),
            target_uuid=str(event.target_entity_uuid),
            outcome=outcome,
            forced_key=None,
            prone_key=None,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 20, slot.source_event_cursor),
        content_attributions=_behavior_content_attributions(
            event.behavior_binding,
        ),
    )


def _damage_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, DamageAppliedEvent) or event.target_entity_uuid is None:
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    types: list[PresentationDamageType] = []
    for damage in event.damages:
        projected = PresentationDamageType(damage.damage_type.value)
        if projected not in types:
            types.append(projected)
    primary = PresentationDamageType(event.damage_type.value)
    if not types:
        types.append(primary)
    source_uuid = _identified_uuid_or_none(event, event.source_entity_uuid, perspective)
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"damage:{event.uuid}",
        kind=_NodeKind.DAMAGE,
        slot=slot,
        payload=_DamagePayload(
            source_uuid=source_uuid,
            target_uuid=str(event.target_entity_uuid),
            applied_amount=event.applied_damage,
            resulting_hp=event.resulting_normal_hp,
            damage_types=tuple(types),
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 40, slot.source_event_cursor),
    )


def _heal_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, HealEvent) or event.target_entity_uuid is None:
        return None
    if event.actual_healing <= 0:
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    resulting_hp = (
        event.resulting_normal_hp
        if event.resulting_normal_hp is not None
        else event.resulting_hp
    )
    if resulting_hp is None:
        return None
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"heal:{event.uuid}",
        kind=_NodeKind.HEAL,
        slot=slot,
        payload=_HealPayload(
            source_uuid=_identified_uuid_or_none(
                event,
                event.source_entity_uuid,
                perspective,
            ),
            target_uuid=str(event.target_entity_uuid),
            amount=event.actual_healing,
            resulting_hp=resulting_hp,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 40, slot.source_event_cursor),
    )


def _lifecycle_cause_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    entity_uuid = event.entity_uuid if isinstance(
        event,
        (ReviveEvent, InstantDeathEvent, DeathSaveEvent),
    ) else None
    if entity_uuid is None or not _identity_allowed(event, entity_uuid, perspective):
        return None
    if isinstance(event, ReviveEvent):
        cause_kind = LifecycleCauseKind.REVIVE
        outcome = None
    elif isinstance(event, InstantDeathEvent):
        cause_kind = LifecycleCauseKind.INSTANT_DEATH
        outcome = None
    elif isinstance(event, DeathSaveEvent):
        cause_kind = LifecycleCauseKind.DEATH_SAVE
        outcome = _death_save_outcome(event)
    else:
        return None
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"lifecycle-cause:{event.uuid}",
        kind=_NodeKind.LIFECYCLE_CAUSE,
        slot=slot,
        payload=_LifecycleCausePayload(
            entity_uuid=str(entity_uuid),
            cause_kind=cause_kind,
            source_uuid=_identified_uuid_or_none(
                event,
                event.source_entity_uuid,
                perspective,
            ),
            death_save_outcome=outcome,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 30, slot.source_event_cursor),
    )


def _life_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, LifeStateChangeEvent):
        return None
    if not _identity_allowed(event, event.entity_uuid, perspective):
        return None
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"life:{event.uuid}",
        kind=_NodeKind.LIFE,
        slot=slot,
        payload=_LifePayload(
            entity_uuid=str(event.entity_uuid),
            previous=event.previous_state,
            current=event.new_state,
            reason=event.reason,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 50, slot.source_event_cursor),
    )


def _condition_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)):
        return None
    if event.target_entity_uuid is None:
        return None
    category = event.condition.condition_category
    if category is ConditionCategory.INTERNAL:
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"condition:{event.uuid}",
        kind=_NodeKind.CONDITION,
        slot=slot,
        payload=_ConditionPayload(
            target_uuid=str(event.target_entity_uuid),
            condition_semantic_key=event.condition.get_semantic_key(),
            condition_name=event.condition.name or "Condition",
            condition_category=category.value,
            operation=(
                ConditionOperation.APPLIED
                if isinstance(event, ConditionApplicationEvent)
                else ConditionOperation.REMOVED
            ),
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 40, slot.source_event_cursor),
        content_attributions=_behavior_content_attributions(
            event.condition.behavior_binding,
        ),
    )


def _action_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, ActionEvent):
        return None
    if event.application_index is not None:
        # MULTI_ENTITY/POSITION_AOE convolution rows are technical
        # applications of the authored root action. Their descendants retain
        # exact lineage ancestry and are reparented to that root below; exposing
        # the application row itself would manufacture one duplicate Action
        # cue per target.
        return None
    if event.behavior_binding is None:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    targets: list[str] = []
    for target_uuid in (
        *((event.target_entity_uuid,) if event.target_entity_uuid else ()),
        *event.declared_target_entity_uuids,
    ):
        target = str(target_uuid)
        if (
            target not in targets
            and _identity_allowed(event, target_uuid, perspective)
        ):
            targets.append(target)
    actor = str(event.source_entity_uuid)
    if actor not in targets and event.target_entity_uuid == event.source_entity_uuid:
        targets.insert(0, actor)
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"action:{event.uuid}",
        kind=_NodeKind.ACTION,
        slot=slot,
        payload=_ActionPayload(
            actor_uuid=actor,
            action_name=event.name or "Action",
            target_uuids=tuple(targets),
            trigger_key=None,
        ),
        lineage=lineage,
        order_key=(
            index.root_order_cursor(lineage, slot.source_event_cursor),
            10,
            slot.source_event_cursor,
        ),
        content_attributions=_behavior_content_attributions(
            event.behavior_binding,
        ),
    )


def _light_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, SensoryUpdateEvent):
        return None
    observer_uuid = str(event.observer_uuid)
    if observer_uuid not in perspective.observer_entity_uuids:
        return None
    cells: list[EffectiveLightCell] = []
    for key, light_level in event.effective_light_levels.items():
        position = _parse_position_key(key)
        if position is None:
            raise SubjectiveEventProjectionError(
                f"invalid effective-light position key: {key!r}"
            )
        cells.append(EffectiveLightCell(position=position, light_level=light_level))
    cells.sort(key=lambda cell: cell.position)
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"light:{event.uuid}",
        kind=_NodeKind.LIGHT,
        slot=slot,
        payload=_LightPayload(observer_uuid=observer_uuid, cells=tuple(cells)),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 70, slot.source_event_cursor),
    )


def _spatial_effect_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    """Project only lifecycle geometry proved by exact event-time position grants."""
    event = slot.event
    if not isinstance(event, SpatialEffectChangeEvent):
        return None
    observers = set(perspective.observer_entity_uuids)

    def disclosed(
        positions: tuple[tuple[int, int], ...],
    ) -> tuple[tuple[int, int], ...]:
        return tuple(
            position
            for position in positions
            if observers
            & event.located_position_observer_uuids.get(
                position_evidence_key(position),
                set(),
            )
        )

    affected_positions = disclosed(event.affected_positions)
    previous_positions = disclosed(event.previous_positions)
    if not affected_positions and not previous_positions:
        return None
    anchor_position = (
        event.anchor_position
        if event.anchor_position
        in {*affected_positions, *previous_positions}
        and observers
        & event.located_position_observer_uuids.get(
            position_evidence_key(event.anchor_position),
            set(),
        )
        else None
    )
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"spatial-effect:{event.uuid}",
        kind=_NodeKind.SPATIAL_EFFECT,
        slot=slot,
        payload=_SpatialEffectPayload(
            effect_uuid=str(event.spatial_effect_uuid),
            content_ref=event.spatial_effect_content_ref,
            operation=event.operation,
            layer=event.layer,
            anchor_position=anchor_position,
            affected_positions=affected_positions,
            previous_positions=previous_positions,
        ),
        lineage=lineage,
        order_key=(
            index.root_order_cursor(lineage, slot.source_event_cursor),
            65,
            slot.source_event_cursor,
        ),
    )


def _encounter_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    encounter_uuid: Optional[UUID] = None
    transition: Optional[EncounterTransition] = None
    round_number = 0
    acting_uuid: Optional[UUID] = None
    reason: Optional[str] = None
    terminal = False
    combatants: tuple[UUID, ...] = ()
    if isinstance(event, EncounterStartEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.START
    elif isinstance(event, EncounterEndEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.END
        combatants = tuple(event.combatant_uuids)
        reason = event.reason
        terminal = True
    elif isinstance(event, RoundStartEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.ROUND_START
        round_number = event.round_number
    elif isinstance(event, RoundEndEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.ROUND_END
        round_number = event.round_number
    elif isinstance(event, TurnStartEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.TURN_START
        round_number = event.round_number
        acting_uuid = event.entity_uuid
    elif isinstance(event, TurnEndEvent):
        encounter_uuid = event.encounter_uuid
        transition = EncounterTransition.TURN_END
        round_number = event.round_number
        acting_uuid = event.entity_uuid
    if encounter_uuid is None or transition is None:
        return None
    projected_combatants = tuple(
        str(entity_uuid)
        for entity_uuid in combatants
        if _identity_allowed(event, entity_uuid, perspective)
    )
    projected_actor = (
        str(acting_uuid)
        if acting_uuid is not None
        and _identity_allowed(event, acting_uuid, perspective)
        else None
    )
    lineage = str(event.lineage_uuid)
    return _NodeSpec(
        key=f"encounter:{event.uuid}",
        kind=_NodeKind.ENCOUNTER,
        slot=slot,
        payload=_EncounterPayload(
            encounter_uuid=str(encounter_uuid),
            transition=transition,
            round_number=round_number,
            acting_entity_uuid=projected_actor,
            reason=reason,
            terminal_barrier=terminal,
            projected_combatant_uuids=projected_combatants,
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 80, slot.source_event_cursor),
    )


def _add_patch_backed_nodes(
    batch: CausalEventBatch,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
    add: object,
) -> None:
    """Create cues that require a complete already-projected reducer value."""
    add_node = add
    if not callable(add_node):
        raise TypeError("patch-backed node sink must be callable")
    door_events = [
        slot
        for slot in index.completions
        if isinstance(slot.event, SpatialChangeEvent)
        and slot.event.object_uuid is not None
        and slot.event.object_is_open is not None
    ]
    item_events = [
        slot
        for slot in index.completions
        if isinstance(slot.event, ItemLocationStateEvent)
    ]
    for patch_index, patch in enumerate(batch.patches):
        if isinstance(patch, DoorStatePatch):
            matching = [
                slot
                for slot in door_events
                if isinstance(slot.event, SpatialChangeEvent)
                and str(slot.event.object_uuid) == patch.object_uuid
                and slot.event.object_is_open == patch.is_open
            ]
            if not matching:
                continue
            source_slot = matching[-1]
            lineage = str(source_slot.event.lineage_uuid)
            add_node(
                _NodeSpec(
                    key=f"door:{source_slot.event.uuid}:{patch_index}",
                    kind=_NodeKind.DOOR,
                    slot=source_slot,
                    payload=_DoorPayload(
                        object_uuid=patch.object_uuid,
                        position=patch.position,
                        is_open=patch.is_open,
                    ),
                    lineage=lineage,
                    order_key=(index.root_order_cursor(lineage, source_slot.source_event_cursor), 70, source_slot.source_event_cursor, patch_index),
                )
            )
        elif isinstance(patch, VisualLoadoutReplacePatch):
            entity_uuid = patch.loadout.entity_uuid
            matching = [
                slot
                for slot in item_events
                if isinstance(slot.event, ItemLocationStateEvent)
                and str(slot.event.owner_uuid or slot.event.source_entity_uuid) == entity_uuid
                and _identity_allowed(
                    slot.event,
                    slot.event.owner_uuid or slot.event.source_entity_uuid,
                    perspective,
                )
            ]
            if not matching:
                continue
            source_slot = matching[-1]
            lineage = str(source_slot.event.lineage_uuid)
            add_node(
                _NodeSpec(
                    key=f"equipment:{source_slot.event.uuid}:{patch_index}",
                    kind=_NodeKind.EQUIPMENT,
                    slot=source_slot,
                    payload=_EquipmentPayload(
                        entity_uuid=entity_uuid,
                        visual_loadout=patch.loadout,
                    ),
                    lineage=lineage,
                    order_key=(index.root_order_cursor(lineage, source_slot.source_event_cursor), 70, source_slot.source_event_cursor, patch_index),
                )
            )


def _add_effective_handler_nodes(
    batch: CausalEventBatch,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
    nodes: list[_NodeSpec],
    add: object,
) -> dict[str, str]:
    """Project exact state-changing reactions that have no specialized cue.

    Handler execution stays an internal engine concern. Only authenticated
    reaction evidence retained on the causal event lineage reaches this
    boundary, where it becomes the same closed action-root DTO used by ordinary
    authored actions. A specialized cue that already carries the handler as its
    behavior/provider remains the single presentation root.
    """

    add_node = add
    if not callable(add_node):
        raise TypeError("handler presentation node sink must be callable")

    parent_by_emitted_lineage: dict[str, str] = {}
    evidence_by_dispatch: dict[
        int,
        tuple[EffectiveHandlerPresentation, ProjectedEventSlot],
    ] = {}
    for carrier_slot in batch.slots:
        for evidence in carrier_slot.event.effective_handler_presentations:
            current = evidence_by_dispatch.get(evidence.dispatch_index)
            if (
                current is None
                or carrier_slot.event.phase is EventPhase.COMPLETION
                or carrier_slot.source_event_cursor > current[1].source_event_cursor
            ):
                evidence_by_dispatch[evidence.dispatch_index] = (
                    evidence,
                    carrier_slot,
                )

    for evidence, carrier_slot in evidence_by_dispatch.values():
        trigger_slot = index.slot_by_event_uuid.get(
            evidence.triggering_event_uuid,
        )
        if trigger_slot is None:
            continue
        trigger = trigger_slot.event
        visibility_event = carrier_slot.event
        if not _identity_allowed(
            visibility_event,
            evidence.source_entity_uuid,
            perspective,
        ):
            continue
        if _specialized_node_represents_handler(nodes, evidence):
            continue
        if (
            evidence.outcome is HandlerDispatchOutcome.EMITTED_EVENTS
            and not _handler_has_delivered_emission(nodes, evidence)
        ):
            continue

        actor_uuid = str(evidence.source_entity_uuid)
        targets: list[str] = []
        target_uuid = trigger.target_entity_uuid
        if (
            target_uuid is not None
            and _identity_allowed(visibility_event, target_uuid, perspective)
        ):
            targets.append(str(target_uuid))
        if target_uuid == evidence.source_entity_uuid and actor_uuid not in targets:
            targets.insert(0, actor_uuid)

        key = (
            f"handler-action:{evidence.dispatch_index}:"
            f"{evidence.triggering_event_uuid}"
        )
        lineage = (
            f"handler:{evidence.dispatch_index}:"
            f"{evidence.triggering_lineage_uuid}"
        )
        node = _NodeSpec(
            key=key,
            kind=_NodeKind.ACTION,
            slot=trigger_slot,
            payload=_ActionPayload(
                actor_uuid=actor_uuid,
                action_name=evidence.handler_name,
                target_uuids=tuple(targets),
                trigger_key=_nearest_visible_handler_trigger_key(
                    nodes,
                    index=index,
                    triggering_lineage=str(evidence.triggering_lineage_uuid),
                ),
            ),
            lineage=lineage,
            order_key=(
                index.root_order_cursor(
                    str(evidence.triggering_lineage_uuid),
                    trigger_slot.source_event_cursor,
                ),
                15,
                trigger_slot.source_event_cursor,
                evidence.dispatch_index,
            ),
            content_attributions=_behavior_content_attributions(
                evidence.behavior_binding,
            ),
        )
        add_node(node)
        for emitted_lineage_uuid in evidence.emitted_lineage_uuids:
            emitted_lineage = str(emitted_lineage_uuid)
            existing = parent_by_emitted_lineage.get(emitted_lineage)
            if existing is not None and existing != key:
                raise SubjectiveEventProjectionError(
                    "one emitted handler lineage cannot belong to two reactions"
                )
            parent_by_emitted_lineage[emitted_lineage] = key
    return parent_by_emitted_lineage


def _handler_has_delivered_emission(
    nodes: list[_NodeSpec],
    evidence: EffectiveHandlerPresentation,
) -> bool:
    """Require emission-only reactions to retain a visible semantic result."""

    emitted_lineages = {
        str(lineage_uuid) for lineage_uuid in evidence.emitted_lineage_uuids
    }
    return any(node.lineage in emitted_lineages for node in nodes)


def _nearest_visible_handler_trigger_key(
    nodes: list[_NodeSpec],
    *,
    index: _BatchIndex,
    triggering_lineage: str,
) -> Optional[str]:
    """Resolve the nearest delivered action-like cue that caused a reaction."""

    trigger_kinds = {
        _NodeKind.ACTION,
        _NodeKind.ATTACK,
        _NodeKind.SPELL,
        _NodeKind.SHOVE,
        _NodeKind.MOVEMENT,
    }
    for lineage in index.ancestors(triggering_lineage, include_self=True):
        candidates = [
            node
            for node in nodes
            if node.lineage == lineage and node.kind in trigger_kinds
        ]
        if candidates:
            return min(candidates, key=lambda node: (node.order_key, node.key)).key
    return None


def _specialized_node_represents_handler(
    nodes: list[_NodeSpec],
    evidence: EffectiveHandlerPresentation,
) -> bool:
    """Return whether a first-class cue already authenticates this reaction."""

    specialized_kinds = {
        _NodeKind.ATTACK,
        _NodeKind.SPELL,
        _NodeKind.COUNTERSPELL,
        _NodeKind.ITEM,
        _NodeKind.SHOVE,
    }
    emitted_lineages = {
        str(lineage_uuid) for lineage_uuid in evidence.emitted_lineage_uuids
    }
    definition_ref = evidence.behavior_binding.definition_ref
    return any(
        node.lineage in emitted_lineages
        and node.kind in specialized_kinds
        and any(
            isinstance(
                attribution,
                (
                    UnrootedBehaviorPresentationAttribution,
                    RootedBehaviorPresentationAttribution,
                ),
            )
            and (
                attribution.definition_ref == definition_ref
                or attribution.provided_by_ref == definition_ref
            )
            for attribution in node.content_attributions
        )
        for node in nodes
    )


def _attach_semantic_nodes(
    *,
    nodes: list[_NodeSpec],
    nodes_by_key: dict[str, _NodeSpec],
    semantic_key_by_lineage: dict[str, str],
    spell_application_by_lineage: dict[str, tuple[str, _SpellApplication]],
    index: _BatchIndex,
    perspective: SubjectivePerspective,
    handler_parent_by_lineage: dict[str, str],
    add: object,
) -> None:
    """Reparent visible descendants across hidden technical engine nodes."""
    del perspective
    add_node = add
    if not callable(add_node):
        raise TypeError("semantic node sink must be callable")

    for node in tuple(nodes):
        if node.kind in {
            _NodeKind.ENCOUNTER,
            _NodeKind.MOVEMENT,
            _NodeKind.LIFECYCLE_CAUSE,
            _NodeKind.LIFE,
        }:
            continue
        handler_parent_key = handler_parent_by_lineage.get(node.lineage)
        handler_parent = (
            nodes_by_key.get(handler_parent_key)
            if handler_parent_key is not None
            else None
        )
        parent_key = (
            handler_parent.key
            if handler_parent is not None
            and _can_parent(handler_parent, node)
            else _nearest_compatible_parent(
                node,
                semantic_key_by_lineage=semantic_key_by_lineage,
                nodes_by_key=nodes_by_key,
                index=index,
            )
        )
        node.parent_key = parent_key

    for action in [
        node for node in nodes if node.kind is _NodeKind.ACTION
    ]:
        payload = action.payload
        if not isinstance(payload, _ActionPayload):
            continue
        targets = list(payload.target_uuids)
        for child in nodes:
            if child.parent_key != action.key:
                continue
            for child_target in _action_child_target_uuids(child):
                if child_target not in targets:
                    targets.append(child_target)
        action.payload = _ActionPayload(
            actor_uuid=payload.actor_uuid,
            action_name=payload.action_name,
            target_uuids=tuple(targets),
            trigger_key=payload.trigger_key,
        )

    damage_nodes = [node for node in nodes if node.kind is _NodeKind.DAMAGE]
    life_nodes = [node for node in nodes if node.kind is _NodeKind.LIFE]
    for life in life_nodes:
        life_payload = life.payload
        if not isinstance(life_payload, _LifePayload):
            continue
        parent_key = _nearest_parent_of_kinds(
            life.lineage,
            kinds={_NodeKind.HEAL, _NodeKind.LIFECYCLE_CAUSE},
            semantic_key_by_lineage=semantic_key_by_lineage,
            nodes_by_key=nodes_by_key,
            index=index,
        )
        if parent_key is None:
            parent_key = _matching_damage_parent(
                life,
                damage_nodes=damage_nodes,
                index=index,
            )
        if parent_key is None and life_payload.reason in {
            LifeStateChangeReason.DIRECT_STATE_CHECK,
            LifeStateChangeReason.INSTANT_DEATH,
            LifeStateChangeReason.REVIVAL,
        }:
            cause_kind = (
                LifecycleCauseKind.DIRECT_STATE_CHECK
                if life_payload.reason is LifeStateChangeReason.DIRECT_STATE_CHECK
                else LifecycleCauseKind.INSTANT_DEATH
                if life_payload.reason is LifeStateChangeReason.INSTANT_DEATH
                else LifecycleCauseKind.REVIVE
            )
            cause = _NodeSpec(
                key=f"lifecycle-cause:synthetic:{life.slot.event.uuid}",
                kind=_NodeKind.LIFECYCLE_CAUSE,
                slot=life.slot,
                payload=_LifecycleCausePayload(
                    entity_uuid=life_payload.entity_uuid,
                    cause_kind=cause_kind,
                    source_uuid=None,
                    death_save_outcome=None,
                ),
                lineage=f"synthetic:{life.lineage}",
                order_key=(life.order_key[0], 30, life.slot.source_event_cursor),
            )
            add_node(cause)
            parent_key = cause.key
        life.parent_key = parent_key

    # Drop lifecycle leaves that cannot satisfy the exact one-transition contract,
    # and drop life facts whose causing impact cannot be proven in this batch.
    valid_life = {node.key for node in life_nodes if node.parent_key is not None}
    nodes[:] = [
        node
        for node in nodes
        if node.kind is not _NodeKind.LIFE or node.key in valid_life
    ]
    nodes_by_key.clear()
    nodes_by_key.update((node.key, node) for node in nodes)
    lifecycle_nodes = [
        node for node in nodes if node.kind is _NodeKind.LIFECYCLE_CAUSE
    ]
    for cause in lifecycle_nodes:
        children = [
            node
            for node in nodes
            if node.kind is _NodeKind.LIFE and node.parent_key == cause.key
        ]
        if len(children) != 1:
            nodes.remove(cause)
            nodes_by_key.pop(cause.key, None)

    # Effect attachment to spell applications is explicit and duplicate-safe.
    for node in tuple(nodes):
        if node.parent_key is None:
            continue
        parent = nodes_by_key.get(node.parent_key)
        if parent is None or parent.kind is not _NodeKind.SPELL:
            continue
        application_match: Optional[_SpellApplication] = None
        for ancestor in index.ancestors(node.lineage, include_self=True):
            match = spell_application_by_lineage.get(ancestor)
            if match is not None and match[0] == parent.key:
                application_match = match[1]
                break
        parent_payload = parent.payload
        if (
            application_match is None
            and isinstance(parent_payload, _SpellPayload)
            and isinstance(node.payload, _SpatialEffectPayload)
        ):
            position = (
                node.payload.anchor_position
                or next(
                    iter(
                        (
                            *node.payload.affected_positions,
                            *node.payload.previous_positions,
                        )
                    ),
                    None,
                )
            )
            if position is not None:
                application_match = _SpellApplication(
                    source_lineage=node.lineage,
                    outcome=SpellApplicationOutcome.AUTOMATIC,
                    target_uuid=None,
                    position=position,
                )
                parent_payload.applications.append(application_match)
        if application_match is None and isinstance(parent_payload, _SpellPayload):
            if len(parent_payload.applications) == 1:
                application_match = parent_payload.applications[0]
        if application_match is None:
            node.parent_key = None
            continue
        if not isinstance(parent_payload, _SpellPayload) or not _spell_effect_matches(
            parent_payload,
            application_match,
            node,
        ):
            node.parent_key = None
            continue
        application_match.effect_keys.append(node.key)
        app_index = (
            parent_payload.applications.index(application_match)
            if isinstance(parent_payload, _SpellPayload)
            else 0
        )
        node.order_key = (app_index, node.slot.source_event_cursor)

    for node in nodes:
        if node.kind is not _NodeKind.FORCED or node.parent_key is None:
            continue
        parent = nodes_by_key.get(node.parent_key)
        payload = node.payload
        if parent is None or not isinstance(payload, _ForcedPayload):
            continue
        if parent.kind is _NodeKind.SHOVE:
            cause = ForcedMovementCause.SHOVE
        elif parent.kind is _NodeKind.SPELL:
            cause = ForcedMovementCause.SPELL
        else:
            cause = ForcedMovementCause.RULE_EFFECT
        node.payload = _ForcedPayload(
            entity_uuid=payload.entity_uuid,
            source_uuid=payload.source_uuid,
            cause=cause,
            start_position=payload.start_position,
            end_position=payload.end_position,
            duration_ms=payload.duration_ms,
        )

    # Shove has a deliberately closed outcome-dependent child surface.
    for shove in [node for node in nodes if node.kind is _NodeKind.SHOVE]:
        payload = shove.payload
        if not isinstance(payload, _ShovePayload):
            continue
        forced = [
            node
            for node in nodes
            if node.parent_key == shove.key and node.kind is _NodeKind.FORCED
        ]
        prone = [
            node
            for node in nodes
            if node.parent_key == shove.key
            and node.kind is _NodeKind.CONDITION
            and isinstance(node.payload, _ConditionPayload)
            and node.payload.condition_name == "Prone"
            and node.payload.operation is ConditionOperation.APPLIED
        ]
        if payload.outcome is ShoveOutcome.SUCCEEDED_PUSH:
            if len(forced) != 1:
                nodes.remove(shove)
                nodes_by_key.pop(shove.key, None)
                for child in forced:
                    nodes.remove(child)
                    nodes_by_key.pop(child.key, None)
                continue
            chosen = forced[0]
            shove.payload = _ShovePayload(
                actor_uuid=payload.actor_uuid,
                target_uuid=payload.target_uuid,
                outcome=payload.outcome,
                forced_key=chosen.key,
                prone_key=None,
            )
        elif payload.outcome is ShoveOutcome.SUCCEEDED_PRONE:
            if len(prone) != 1:
                nodes.remove(shove)
                nodes_by_key.pop(shove.key, None)
                continue
            chosen = prone[0]
            shove.payload = _ShovePayload(
                actor_uuid=payload.actor_uuid,
                target_uuid=payload.target_uuid,
                outcome=payload.outcome,
                forced_key=None,
                prone_key=chosen.key,
            )
        else:
            for child in forced + prone:
                child.parent_key = None

    # A forced move is unrepresentable without a delivered actor action.
    for node in tuple(nodes):
        if node.kind is _NodeKind.FORCED and (
            node.parent_key is None or node.parent_key not in nodes_by_key
        ):
            nodes.remove(node)
            nodes_by_key.pop(node.key, None)


def _nearest_compatible_parent(
    node: _NodeSpec,
    *,
    semantic_key_by_lineage: dict[str, str],
    nodes_by_key: dict[str, _NodeSpec],
    index: _BatchIndex,
) -> Optional[str]:
    for ancestor in index.ancestors(node.lineage):
        key = semantic_key_by_lineage.get(ancestor)
        if key is None or key == node.key:
            continue
        parent = nodes_by_key.get(key)
        if parent is not None and _can_parent(parent, node):
            return key
    return None


def _nearest_parent_of_kinds(
    lineage: str,
    *,
    kinds: set[_NodeKind],
    semantic_key_by_lineage: dict[str, str],
    nodes_by_key: dict[str, _NodeSpec],
    index: _BatchIndex,
) -> Optional[str]:
    for ancestor in index.ancestors(lineage):
        key = semantic_key_by_lineage.get(ancestor)
        parent = nodes_by_key.get(key) if key is not None else None
        if parent is not None and parent.kind in kinds:
            return parent.key
    return None


def _matching_damage_parent(
    life: _NodeSpec,
    *,
    damage_nodes: list[_NodeSpec],
    index: _BatchIndex,
) -> Optional[str]:
    payload = life.payload
    if not isinstance(payload, _LifePayload):
        return None
    life_ancestors = index.ancestors(life.lineage, include_self=True)
    life_distance = {lineage: offset for offset, lineage in enumerate(life_ancestors)}
    candidates: list[tuple[int, int, str]] = []
    for damage in damage_nodes:
        damage_payload = damage.payload
        if not isinstance(damage_payload, _DamagePayload):
            continue
        if damage_payload.target_uuid != payload.entity_uuid:
            continue
        if damage.slot.source_event_cursor > life.slot.source_event_cursor:
            continue
        damage_ancestors = index.ancestors(damage.lineage, include_self=True)
        shared = [lineage for lineage in damage_ancestors if lineage in life_distance]
        if not shared:
            continue
        closest = min(
            life_distance[lineage] + damage_ancestors.index(lineage)
            for lineage in shared
        )
        candidates.append((closest, -damage.slot.source_event_cursor, damage.key))
    return min(candidates)[2] if candidates else None


def _can_parent(parent: _NodeSpec, child: _NodeSpec) -> bool:
    parent_kind = parent.kind
    if parent_kind is _NodeKind.ACTION:
        parent_payload = parent.payload
        if not isinstance(parent_payload, _ActionPayload):
            return False
        if child.kind in {
            _NodeKind.ATTACK,
            _NodeKind.SPELL,
            _NodeKind.SHOVE,
        }:
            child_payload = child.payload
            child_actor = (
                child_payload.actor_uuid
                if isinstance(
                    child_payload,
                    (_AttackPayload, _SpellPayload, _ShovePayload),
                )
                else None
            )
            return child_actor == parent_payload.actor_uuid
        if child.kind in {
            _NodeKind.DOOR,
            _NodeKind.LIGHT,
            _NodeKind.SPATIAL_EFFECT,
            _NodeKind.EQUIPMENT,
        }:
            return True
        if isinstance(child.payload, _DamagePayload):
            return child.payload.source_uuid == parent_payload.actor_uuid
        if isinstance(child.payload, _HealPayload):
            return child.payload.source_uuid == parent_payload.actor_uuid
        if isinstance(child.payload, _ConditionPayload):
            return True
        if isinstance(child.payload, _ForcedPayload):
            return child.payload.source_uuid == parent_payload.actor_uuid
        return False
    if parent_kind is _NodeKind.MOVEMENT:
        return child.kind in {_NodeKind.ATTACK, _NodeKind.SPELL, _NodeKind.SHOVE}
    if parent_kind in {_NodeKind.ATTACK, _NodeKind.ITEM}:
        if child.kind not in {
            _NodeKind.DAMAGE,
            _NodeKind.HEAL,
            _NodeKind.CONDITION,
        }:
            return False
        return _action_effect_ownership_matches(parent, child)
    if parent_kind is _NodeKind.SPELL:
        return child.kind in {
            _NodeKind.DAMAGE,
            _NodeKind.HEAL,
            _NodeKind.CONDITION,
            _NodeKind.FORCED,
            _NodeKind.SPATIAL_EFFECT,
        }
    if parent_kind is _NodeKind.SHOVE:
        if child.kind is _NodeKind.FORCED:
            return (
                isinstance(parent.payload, _ShovePayload)
                and isinstance(child.payload, _ForcedPayload)
                and child.payload.source_uuid == parent.payload.actor_uuid
                and child.payload.entity_uuid == parent.payload.target_uuid
            )
        return (
            child.kind is _NodeKind.CONDITION
            and isinstance(parent.payload, _ShovePayload)
            and isinstance(child.payload, _ConditionPayload)
            and child.payload.target_uuid == parent.payload.target_uuid
            and child.payload.condition_name == "Prone"
            and child.payload.operation is ConditionOperation.APPLIED
        )
    if parent_kind in {
        _NodeKind.DAMAGE,
        _NodeKind.HEAL,
        _NodeKind.LIFECYCLE_CAUSE,
    }:
        return child.kind is _NodeKind.LIFE
    return False


def _action_child_target_uuids(child: _NodeSpec) -> tuple[str, ...]:
    payload = child.payload
    if isinstance(payload, (_AttackPayload, _ShovePayload)):
        return (payload.target_uuid,)
    if isinstance(payload, _SpellPayload):
        return tuple(
            application.target_uuid
            for application in payload.applications
            if application.target_uuid is not None
        )
    if isinstance(payload, (_DamagePayload, _HealPayload, _ConditionPayload)):
        return (payload.target_uuid,)
    if isinstance(payload, _ForcedPayload):
        return (payload.entity_uuid,)
    if isinstance(payload, _EquipmentPayload):
        return (payload.entity_uuid,)
    if isinstance(payload, _LightPayload):
        return (payload.observer_uuid,)
    return ()


def _action_effect_ownership_matches(parent: _NodeSpec, child: _NodeSpec) -> bool:
    """Require direct action effects to name the action's exact safe participants."""
    if isinstance(parent.payload, _AttackPayload):
        actor_uuid = parent.payload.actor_uuid
        target_uuid = parent.payload.target_uuid
    elif isinstance(parent.payload, _ItemPayload):
        actor_uuid = parent.payload.actor_uuid
        target_uuid = parent.payload.actor_uuid
    else:
        return False
    if isinstance(child.payload, _DamagePayload):
        return (
            child.payload.source_uuid == actor_uuid
            and child.payload.target_uuid == target_uuid
        )
    if isinstance(child.payload, _HealPayload):
        return (
            child.payload.source_uuid == actor_uuid
            and child.payload.target_uuid == target_uuid
        )
    if isinstance(child.payload, _ConditionPayload):
        return child.payload.target_uuid == target_uuid
    return False


def _spell_effect_matches(
    spell: _SpellPayload,
    application: _SpellApplication,
    effect: _NodeSpec,
) -> bool:
    """Validate one direct spell effect against its exact delivered application."""
    target_uuid = application.target_uuid
    if isinstance(effect.payload, _DamagePayload):
        return (
            target_uuid is not None
            and effect.payload.target_uuid == target_uuid
            and effect.payload.source_uuid == spell.actor_uuid
        )
    if isinstance(effect.payload, _HealPayload):
        return (
            target_uuid is not None
            and effect.payload.target_uuid == target_uuid
            and effect.payload.source_uuid == spell.actor_uuid
        )
    if isinstance(effect.payload, _ConditionPayload):
        return target_uuid is not None and effect.payload.target_uuid == target_uuid
    if isinstance(effect.payload, _ForcedPayload):
        return (
            target_uuid is not None
            and effect.payload.entity_uuid == target_uuid
            and effect.payload.source_uuid == spell.actor_uuid
        )
    if isinstance(effect.payload, _SpatialEffectPayload):
        geometry = {
            *effect.payload.affected_positions,
            *effect.payload.previous_positions,
        }
        return (
            application.target_uuid is None
            and application.position is not None
            and application.position in geometry
        )
    return False


def _materialize_node(
    node: _NodeSpec,
    coordinates: PresentationNodeCoordinates,
) -> SubjectivePresentationCue:
    common = {
        "presentation_cursor": coordinates.presentation_cursor,
        "presentation_id": coordinates.presentation_id,
        "parent_presentation_id": coordinates.parent_presentation_id,
        "child_presentation_ids": coordinates.child_presentation_ids,
        "source_event_cursor": node.slot.source_event_cursor,
        "source_event_uuid": str(node.slot.event.uuid),
        "content_attributions": node.content_attributions,
    }
    payload = node.payload
    if isinstance(payload, _MovementPayload):
        return MovementPresentationCue(
            **common,
            entity_uuid=payload.entity_uuid,
            locomotion_family=payload.locomotion_family,
            trajectory_family=payload.trajectory_family,
            anchors=payload.anchors,
            connector=payload.connector,
            endpoint_outcome=payload.endpoint_outcome,
            perception_commit="observation_frame",
        )
    if isinstance(payload, _ActionPayload):
        return ActionPresentationCue(
            **common,
            actor_uuid=payload.actor_uuid,
            action_name=payload.action_name,
            target_uuids=payload.target_uuids,
            trigger_presentation_id=(
                coordinates.presentation_ids_by_key[payload.trigger_key]
                if payload.trigger_key is not None
                else None
            ),
            effect_presentation_ids=coordinates.child_presentation_ids,
        )
    if isinstance(payload, _AttackPayload):
        return AttackPresentationCue(
            **common,
            actor_uuid=payload.actor_uuid,
            target_uuid=payload.target_uuid,
            action_name=payload.action_name,
            outcome=payload.outcome,
            delivery=payload.delivery,
            weapon_slot=payload.weapon_slot,
            damage_types=payload.damage_types,
            projectile_type=payload.projectile_type,
            impact_effect_presentation_ids=coordinates.child_presentation_ids,
        )
    if isinstance(payload, _SpellPayload):
        targets = tuple(
            SpellTargetPresentation(
                application_index=index,
                application_id=f"{coordinates.presentation_id}:application:{index}",
                outcome=application.outcome,
                target_uuid=application.target_uuid,
                position=application.position,
                effect_presentation_ids=tuple(
                    coordinates.presentation_ids_by_key[key]
                    for key in application.effect_keys
                ),
            )
            for index, application in enumerate(payload.applications)
        )
        return SpellPresentationCue(
            **common,
            actor_uuid=payload.actor_uuid,
            spell_id=payload.spell_id,
            spell_name=payload.spell_name,
            spell_school=payload.spell_school,
            spell_level=payload.spell_level,
            delivery=payload.delivery,
            targets=targets,
            projectile_type=payload.projectile_type,
            area=payload.area,
        )
    if isinstance(payload, _CounterspellPayload):
        return CounterspellPresentationCue(
            **common,
            reactor_uuid=payload.reactor_uuid,
            incoming_caster_uuid=payload.incoming_caster_uuid,
            incoming_spell_level=payload.incoming_spell_level,
            counterspell_slot_level=payload.counterspell_slot_level,
            resolution=payload.resolution,
        )
    if isinstance(payload, _ItemPayload):
        return ItemActionPresentationCue(
            **common,
            actor_uuid=payload.actor_uuid,
            item_uuid=payload.item_uuid,
            item_kind=payload.item_kind,
            action_kind=ItemActionKind.DRINK,
            effect_frame=8,
            playback_speed=1.0,
            hidden_slots=(
                ActorVisualSlot.WEAPON,
                ActorVisualSlot.WEAPON_GLOW,
                ActorVisualSlot.OFFHAND,
            ),
            effect_presentation_ids=coordinates.child_presentation_ids,
        )
    if isinstance(payload, _ShovePayload):
        return ShovePresentationCue(
            **common,
            actor_uuid=payload.actor_uuid,
            target_uuid=payload.target_uuid,
            outcome=payload.outcome,
            contact_frame=7,
            playback_speed=1.35,
            forced_movement_presentation_id=(
                coordinates.presentation_ids_by_key[payload.forced_key]
                if payload.forced_key is not None
                else None
            ),
            prone_condition_presentation_id=(
                coordinates.presentation_ids_by_key[payload.prone_key]
                if payload.prone_key is not None
                else None
            ),
        )
    if isinstance(payload, _ForcedPayload):
        if coordinates.parent_presentation_id is None:
            raise SubjectiveEventProjectionError(
                "forced movement requires a delivered actor action"
            )
        return ForcedMovementPresentationCue(
            **common,
            entity_uuid=payload.entity_uuid,
            source_uuid=payload.source_uuid,
            cause=payload.cause,
            actor_action_presentation_id=coordinates.parent_presentation_id,
            start_position=payload.start_position,
            end_position=payload.end_position,
            duration_ms=payload.duration_ms,
            brace_frame=5,
            playback_speed=1.25,
        )
    if isinstance(payload, _DamagePayload):
        return DamagePresentationCue(
            **common,
            source_uuid=payload.source_uuid,
            target_uuid=payload.target_uuid,
            applied_amount=payload.applied_amount,
            resulting_hp=payload.resulting_hp,
            damage_types=payload.damage_types,
        )
    if isinstance(payload, _HealPayload):
        return HealPresentationCue(
            **common,
            source_uuid=payload.source_uuid,
            target_uuid=payload.target_uuid,
            amount=payload.amount,
            resulting_hp=payload.resulting_hp,
        )
    if isinstance(payload, _LifecycleCausePayload):
        return LifecycleCausePresentationCue(
            **common,
            entity_uuid=payload.entity_uuid,
            cause_kind=payload.cause_kind,
            source_uuid=payload.source_uuid,
            death_save_outcome=payload.death_save_outcome,
        )
    if isinstance(payload, _LifePayload):
        if coordinates.parent_presentation_id is None:
            raise SubjectiveEventProjectionError(
                "life transition requires a delivered causing impact"
            )
        return LifeStatePresentationCue(
            **common,
            entity_uuid=payload.entity_uuid,
            previous=payload.previous,
            current=payload.current,
            reason=payload.reason,
            causing_effect_presentation_id=coordinates.parent_presentation_id,
        )
    if isinstance(payload, _ConditionPayload):
        return ConditionPresentationCue(
            **common,
            target_uuid=payload.target_uuid,
            condition_semantic_key=payload.condition_semantic_key,
            condition_name=payload.condition_name,
            condition_category=payload.condition_category,
            operation=payload.operation,
        )
    if isinstance(payload, _DoorPayload):
        return DoorPresentationCue(
            **common,
            object_uuid=payload.object_uuid,
            position=payload.position,
            is_open=payload.is_open,
        )
    if isinstance(payload, _LightPayload):
        return LightPresentationCue(
            **common,
            observer_uuid=payload.observer_uuid,
            cells=payload.cells,
        )
    if isinstance(payload, _SpatialEffectPayload):
        return SpatialEffectPresentationCue(
            **common,
            effect_uuid=payload.effect_uuid,
            content_ref=payload.content_ref,
            operation=payload.operation,
            layer=payload.layer,
            anchor_position=payload.anchor_position,
            affected_positions=payload.affected_positions,
            previous_positions=payload.previous_positions,
        )
    if isinstance(payload, _EquipmentPayload):
        return EquipmentPresentationCue(
            **common,
            entity_uuid=payload.entity_uuid,
            visual_loadout=payload.visual_loadout,
        )
    if isinstance(payload, _EncounterPayload):
        return EncounterPresentationCue(
            **common,
            encounter_uuid=payload.encounter_uuid,
            transition=payload.transition,
            round_number=payload.round_number,
            acting_entity_uuid=payload.acting_entity_uuid,
            reason=payload.reason,
            terminal_barrier=payload.terminal_barrier,
            projected_combatant_uuids=payload.projected_combatant_uuids,
        )
    raise SubjectiveEventProjectionError(f"unsupported semantic payload: {type(payload).__name__}")


def _forced_node(
    slot: ProjectedEventSlot,
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
) -> Optional[_NodeSpec]:
    event = slot.event
    if not isinstance(event, ForcedMovementEvent) or event.target_entity_uuid is None:
        return None
    if event.start_position == event.end_position or event.actual_distance <= 0:
        return None
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
        return None
    if not _identity_allowed(event, event.target_entity_uuid, perspective):
        return None
    if not _forced_movement_geometry_allowed(
        event,
        perspective,
        causing_entity_uuid=event.source_entity_uuid,
    ):
        return None
    lineage = str(event.lineage_uuid)
    rendered_distance = math.hypot(
        event.end_position[0] - event.start_position[0],
        event.end_position[1] - event.start_position[1],
    )
    return _NodeSpec(
        key=f"forced:{event.uuid}",
        kind=_NodeKind.FORCED,
        slot=slot,
        payload=_ForcedPayload(
            entity_uuid=str(event.target_entity_uuid),
            source_uuid=str(event.source_entity_uuid),
            cause=ForcedMovementCause.RULE_EFFECT,
            start_position=event.start_position,
            end_position=event.end_position,
            duration_ms=max(260, round(rendered_distance * 220)),
        ),
        lineage=lineage,
        order_key=(index.root_order_cursor(lineage, slot.source_event_cursor), 40, slot.source_event_cursor),
    )


def _identity_allowed(
    event: Event,
    entity_uuid: UUID,
    perspective: SubjectivePerspective,
) -> bool:
    entity_key = str(entity_uuid)
    if entity_key in perspective.controlled_entity_uuids:
        return True
    grants = event.identified_entity_observer_uuids.get(entity_key, set())
    return bool(set(perspective.observer_entity_uuids) & grants)


def _location_allowed(
    event: Event,
    entity_uuid: UUID,
    perspective: SubjectivePerspective,
) -> bool:
    entity_key = str(entity_uuid)
    if entity_key in perspective.controlled_entity_uuids:
        return True
    grants = event.located_entity_observer_uuids.get(entity_key, set())
    return bool(set(perspective.observer_entity_uuids) & grants)


def _forced_movement_geometry_allowed(
    event: ForcedMovementEvent,
    perspective: SubjectivePerspective,
    *,
    causing_entity_uuid: UUID | None = None,
) -> bool:
    """Allow exact displacement only with ownership or both endpoint grants.

    A controlling player may receive their own displacement or a forced path
    caused by their own action. Other observers receive the geometry only when
    one observer in the perspective saw the displaced entity at both the
    event-time start and completion-time destination. The world patch remains
    the safe post-state fallback when either endpoint was hidden.
    """
    controlled = set(perspective.controlled_entity_uuids)
    if (
        str(event.target_entity_uuid) in controlled
        or (
            causing_entity_uuid is not None
            and str(causing_entity_uuid) in controlled
        )
    ):
        return True
    origin = event.located_position_observer_uuids.get(
        position_evidence_key(event.start_position),
        set(),
    )
    destination = event.located_position_observer_uuids.get(
        position_evidence_key(event.end_position),
        set(),
    )
    eligible = origin & destination & set(perspective.observer_entity_uuids)
    return bool(eligible)


def _step_geometry_allowed(
    event: StepMovementEvent,
    perspective: SubjectivePerspective,
) -> bool:
    """Require one authorized observer to have seen both step endpoints."""
    if str(event.source_entity_uuid) in perspective.controlled_entity_uuids:
        return True
    origin = event.located_position_observer_uuids.get(
        position_evidence_key(event.from_position),
        set(),
    )
    destination = event.located_position_observer_uuids.get(
        position_evidence_key(event.to_position),
        set(),
    )
    eligible = origin & destination & set(perspective.observer_entity_uuids)
    return bool(eligible)


def _identified_uuid_or_none(
    event: Event,
    entity_uuid: UUID,
    perspective: SubjectivePerspective,
) -> Optional[str]:
    return str(entity_uuid) if _identity_allowed(event, entity_uuid, perspective) else None


def _behavior_content_attributions(
    binding: BehaviorBinding | None,
    *,
    role: BehaviorPresentationRole = BehaviorPresentationRole.BEHAVIOR,
) -> tuple[PresentationContentAttribution, ...]:
    """Convert one authenticated runtime binding without fabricating identity."""
    if binding is None:
        return ()
    if binding.origin_root_ref is None:
        return (
            UnrootedBehaviorPresentationAttribution(
                role=role,
                definition_ref=binding.definition_ref,
                provided_by_ref=binding.provided_by_ref,
            ),
        )
    return (
        RootedBehaviorPresentationAttribution(
            role=role,
            definition_ref=binding.definition_ref,
            provided_by_ref=binding.provided_by_ref,
            origin_root_ref=binding.origin_root_ref,
        ),
    )


def _source_item_content_attributions(
    event: ActionEvent,
) -> tuple[PresentationContentAttribution, ...]:
    """Project one declaration-time item identity without consulting live state."""
    snapshot = event.source_item_presentation
    if (
        event.source_item_uuid is None
        or snapshot is None
        or snapshot.item_uuid != event.source_item_uuid
        or snapshot.content_ref is None
    ):
        return ()
    return (
        SourceItemPresentationAttribution(
            definition_ref=ContentRef.model_validate(
                snapshot.content_ref.model_dump(mode="python")
            ),
        ),
    )


def _attack_outcome(value: EngineAttackOutcome) -> Optional[AttackOutcome]:
    return {
        EngineAttackOutcome.HIT: AttackOutcome.HIT,
        EngineAttackOutcome.MISS: AttackOutcome.MISS,
        EngineAttackOutcome.CRIT: AttackOutcome.CRITICAL,
        EngineAttackOutcome.CRIT_MISS: AttackOutcome.CRITICAL_MISS,
    }.get(value)


def _weapon_slot(value: WeaponSlot) -> PresentationWeaponSlot:
    return PresentationWeaponSlot(value.value)


def _projectile(value: Optional[str]) -> Optional[PresentationProjectile]:
    if value is None:
        return None
    try:
        return PresentationProjectile(value.strip().lower())
    except ValueError:
        return None


def _spell_application_outcome(event: SpellEvent) -> SpellApplicationOutcome:
    if event.attack_outcome is EngineAttackOutcome.CRIT:
        return SpellApplicationOutcome.CRITICAL
    if event.attack_outcome is EngineAttackOutcome.HIT:
        return SpellApplicationOutcome.HIT
    if event.attack_outcome in {EngineAttackOutcome.MISS, EngineAttackOutcome.CRIT_MISS}:
        return SpellApplicationOutcome.MISS
    if event.save_success is True:
        return SpellApplicationOutcome.SAVE_SUCCEEDED
    if event.save_success is False:
        return SpellApplicationOutcome.SAVE_FAILED
    return SpellApplicationOutcome.AUTOMATIC


def _death_save_outcome(event: DeathSaveEvent) -> DeathSaveOutcome:
    if event.natural_roll == 20:
        return DeathSaveOutcome.CRITICAL_SUCCESS
    if event.natural_roll == 1:
        return DeathSaveOutcome.CRITICAL_FAILURE
    return DeathSaveOutcome.SUCCESS if event.succeeded else DeathSaveOutcome.FAILURE


def _area_geometry(event: SpellEvent) -> Optional[AreaGeometry]:
    area = event.area_geometry
    if isinstance(area, SpherePresentationGeometry):
        return SphereAreaGeometry(center=area.center, radius_feet=area.radius_feet)
    if isinstance(area, ConePresentationGeometry):
        return ConeAreaGeometry(
            origin=area.origin,
            direction=area.direction,
            length_feet=area.length_feet,
            angle_degrees=area.angle_degrees,
        )
    if isinstance(area, LinePresentationGeometry):
        return LineAreaGeometry(
            origin=area.origin,
            direction=area.direction,
            length_feet=area.length_feet,
            width_feet=area.width_feet,
        )
    if isinstance(area, CubePresentationGeometry):
        return CubeAreaGeometry(
            origin=area.origin,
            direction=area.direction,
            size_feet=area.size_feet,
            centered=area.centered,
        )
    if isinstance(area, CylinderPresentationGeometry):
        return CylinderAreaGeometry(
            center=area.center,
            radius_feet=area.radius_feet,
            height_feet=area.height_feet,
        )
    return None


def _parse_position_key(value: str) -> Optional[tuple[int, int]]:
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


canonical_subjective_presentation_mapper = CanonicalSubjectivePresentationMapper()


__all__ = [
    "CanonicalSubjectivePresentationMapper",
    "CausalEventBatch",
    "ProjectedEventSlot",
    "SubjectiveEventProjectionError",
    "canonical_subjective_presentation_mapper",
    "validate_step_against_movement_root",
]
