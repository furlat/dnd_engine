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
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

from dnd.actions import (
    AttackEvent,
    JumpEvent,
    MovementEvent,
    ShoveEvent,
    SpellEvent,
)
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
    MovementKind,
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
    EQUIPMENT = "equipment"
    ENCOUNTER = "encounter"


@dataclass(frozen=True)
class _MovementPayload:
    entity_uuid: str
    movement_kind: MovementKind
    trajectory: tuple[tuple[int, int], ...]
    path_start_index: int
    path_total_steps: int


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


class _BatchIndex:
    """In-batch lineage topology; it never consults EventQueue or registries."""

    def __init__(self, batch: CausalEventBatch) -> None:
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
        for slot in batch.slots:
            lineage = str(slot.event.lineage_uuid)
            event_lineage_by_uuid[slot.event.uuid] = lineage
            self.slot_by_event_uuid[slot.event.uuid] = slot
            self.first_cursor_by_lineage.setdefault(lineage, slot.source_event_cursor)
            if slot.event.phase is EventPhase.COMPLETION and not slot.event.canceled:
                self.completion_by_lineage[lineage] = slot

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

        index = _BatchIndex(source)
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
        if isinstance(event, (MovementEvent, JumpEvent, StepMovementEvent)):
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
            node = _light_node(slot, index=index, perspective=perspective)
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
    _add_movement_nodes(
        index=index,
        perspective=perspective,
        add=add,
        semantic_key_by_lineage=semantic_key_by_lineage,
        reactive_step_lineages=frozenset(
            reactive_step_lineage_by_node_key.values()
        ),
    )
    _attach_movement_reactions(
        nodes=nodes,
        nodes_by_key=nodes_by_key,
        semantic_key_by_lineage=semantic_key_by_lineage,
        reactive_step_lineage_by_node_key=reactive_step_lineage_by_node_key,
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
        step_lineage = _nearest_committed_step_lineage(node, index=index)
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


def _nearest_committed_step_lineage(
    node: _NodeSpec,
    *,
    index: _BatchIndex,
) -> Optional[str]:
    """Return the exact committed movement step that causally owns ``node``."""
    for ancestor in index.ancestors(node.lineage):
        slot = index.completion_by_lineage.get(ancestor)
        if (
            slot is not None
            and isinstance(slot.event, StepMovementEvent)
            and slot.event.committed
        ):
            return ancestor
    return None


def _add_movement_nodes(
    *,
    index: _BatchIndex,
    perspective: SubjectivePerspective,
    add: object,
    semantic_key_by_lineage: dict[str, str],
    reactive_step_lineages: frozenset[str],
) -> None:
    """Coalesce committed steps, starting a segment at every visible reaction.

    Movement-owned Attack, Spell, and Shove cues are pre-edge reactions. The
    owning segment therefore begins with the exact triggering step; later
    nonreactive steps may remain coalesced until the next reaction boundary.
    """
    grouped: dict[str, list[ProjectedEventSlot]] = {}
    root_event_by_lineage: dict[str, MovementEvent] = {}
    for slot in index.completions:
        if not isinstance(slot.event, StepMovementEvent) or not slot.event.committed:
            continue
        step = slot.event
        if not _identity_allowed(step, step.source_entity_uuid, perspective):
            continue
        if not _step_geometry_allowed(step, perspective):
            continue
        root_lineage: Optional[str] = None
        for ancestor in index.ancestors(str(step.lineage_uuid)):
            root_slot = index.completion_by_lineage.get(ancestor)
            if root_slot is not None and isinstance(root_slot.event, MovementEvent):
                root_lineage = ancestor
                root_event_by_lineage[ancestor] = root_slot.event
                break
        root_lineage = root_lineage or str(step.parent_lineage or step.lineage_uuid)
        grouped.setdefault(root_lineage, []).append(slot)

    add_node = add
    if not callable(add_node):
        raise TypeError("movement node sink must be callable")
    for root_lineage, step_slots in grouped.items():
        step_slots.sort(
            key=lambda candidate: (
                candidate.event.path_index
                if isinstance(candidate.event, StepMovementEvent)
                else 0,
                candidate.source_event_cursor,
            )
        )
        segments: list[list[ProjectedEventSlot]] = []
        for slot in step_slots:
            step = slot.event
            if not isinstance(step, StepMovementEvent):
                continue
            if not segments:
                segments.append([slot])
                continue
            previous_slot = segments[-1][-1]
            previous = previous_slot.event
            if not isinstance(previous, StepMovementEvent):
                segments.append([slot])
                continue
            contiguous = (
                step.source_entity_uuid == previous.source_entity_uuid
                and step.total_path_length == previous.total_path_length
                and step.path_index == previous.path_index + 1
                and step.from_position == previous.to_position
                and step.trajectory is previous.trajectory
                and str(step.lineage_uuid) not in reactive_step_lineages
            )
            if contiguous:
                segments[-1].append(slot)
            else:
                segments.append([slot])

        root_event = root_event_by_lineage.get(root_lineage)
        for segment_index, segment in enumerate(segments):
            first = segment[0].event
            last_slot = segment[-1]
            if not isinstance(first, StepMovementEvent):
                continue
            trajectory = (first.from_position,) + tuple(
                step_slot.event.to_position
                for step_slot in segment
                if isinstance(step_slot.event, StepMovementEvent)
            )
            movement_kind = (
                MovementKind.JUMP
                if isinstance(root_event, JumpEvent)
                or first.trajectory is MovementTrajectory.DIRECT_ARC
                else MovementKind.WALK
            )
            key = f"movement:{last_slot.event.uuid}:{segment_index}"
            node = _NodeSpec(
                key=key,
                kind=_NodeKind.MOVEMENT,
                slot=last_slot,
                payload=_MovementPayload(
                    entity_uuid=str(first.source_entity_uuid),
                    movement_kind=movement_kind,
                    trajectory=trajectory,
                    path_start_index=max(0, first.path_index - 1),
                    path_total_steps=max(
                        first.path_index,
                        first.total_path_length - 1,
                    ),
                ),
                lineage=root_lineage,
                order_key=(
                    index.root_order_cursor(
                        root_lineage,
                        last_slot.source_event_cursor,
                    ),
                    10,
                    first.path_index,
                    segment_index,
                ),
                content_attributions=_behavior_content_attributions(
                    root_event.behavior_binding
                    if root_event is not None
                    else None,
                ),
            )
            add_node(node, map_lineage=False)
            for step_slot in segment:
                semantic_key_by_lineage[str(step_slot.event.lineage_uuid)] = key
            semantic_key_by_lineage.setdefault(root_lineage, key)


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
    if not _identity_allowed(event, event.source_entity_uuid, perspective):
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
    if area is not None and not _location_allowed(
        event,
        event.source_entity_uuid,
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
            movement_kind=payload.movement_kind,
            trajectory=payload.trajectory,
            path_start_index=payload.path_start_index,
            path_total_steps=payload.path_total_steps,
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
]
