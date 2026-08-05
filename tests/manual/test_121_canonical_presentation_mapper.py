"""Focused contracts for canonical event-to-player presentation projection."""

from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID, uuid4

import pytest

from dnd.actions import (
    Attack,
    AttackEvent,
    Jump,
    JumpEvent,
    Move,
    MovementEvent,
    Shove,
    ShoveEvent,
    SpellEvent,
)
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.classes.paladin import create_divine_smite_handler
from dnd.conditions import Prone
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.action_types import ActionPresentationKind
from dnd.core.base_actions import ActionEvent
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.combat_log import position_evidence_key
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import (
    BehaviorBinding,
    EffectiveHandlerPresentation,
    HandlerDispatchOutcome,
)
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Damage,
    DamageAppliedEvent,
    DamageRollResultEvent,
    EncounterEndEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    HealEvent,
    LifeStateChangeEvent,
    MovementTrajectory,
    RollModificationOperation,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialEffectChangeEvent,
    StepMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import (
    EquippedVisualPolicy,
    ItemContentRefSnapshot,
    ItemLocation,
    ItemPresentationKind,
    ItemPresentationState,
    ItemRarity,
)
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.presentation_geometry import (
    ConePresentationGeometry,
    CubePresentationGeometry,
)
from dnd.core.spatial_effect_types import (
    SpatialEffectChangeOperation,
    SpatialEffectLayer,
)
from dnd.entity import Entity, EntityConfig
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.traits import ParryFeature
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.abjuration import (
    CounterspellReactionEvent,
    create_shield_reaction_handler,
)
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
)
from dnd.spells.evocation import GustOfWind, Thunderwave
from dnd.spells.transmutation import TelekinesisMove
from tests.engine.support import (
    force_attack_crit,
    force_attack_hit,
    force_attack_miss,
    reset_combat_state,
)
from server.player_replication.journal import SubjectiveFrameProjectionContext
from server.player_replication.mapper import (
    CanonicalSubjectivePresentationMapper,
    CausalEventBatch,
    ProjectedEventSlot,
    SubjectiveEventProjectionError,
)
from server.player_replication_contract import (
    ActiveWeaponSet,
    ActionPresentationCue,
    AttackPresentationCue,
    BehaviorPresentationRole,
    ConeAreaGeometry,
    CubeAreaGeometry,
    CounterspellAutomaticSuccess,
    CounterspellCheckFailure,
    CounterspellPresentationCue,
    ConditionPresentationCue,
    DamagePresentationCue,
    DoorPresentationCue,
    DoorStatePatch,
    EncounterPresentationCue,
    EntityVisualLoadout,
    EquipmentPresentationCue,
    ForcedMovementCause,
    ForcedMovementPresentationCue,
    HealPresentationCue,
    ItemActionPresentationCue,
    LifeStatePresentationCue,
    LightPresentationCue,
    MovementKind,
    MovementPresentationCue,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    PresentationDamageType,
    PresentationProjectile,
    ShoveOutcome,
    ShovePresentationCue,
    RootedBehaviorPresentationAttribution,
    SourceItemPresentationAttribution,
    SpellApplicationOutcome,
    SpellDelivery,
    SpellPresentationCue,
    SpellTargetPresentation,
    SpatialEffectPresentationCue,
    SubjectivePerspective,
    SubjectiveReplicationFrame,
    VisualLoadoutReplacePatch,
    UnrootedBehaviorPresentationAttribution,
)
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


MAPPER = CanonicalSubjectivePresentationMapper()
_EventT = TypeVar("_EventT", bound=Event)


def _content_ref(
    *,
    kind: ContentDefinitionKind,
    content_id: str,
    digest_char: str,
) -> ContentRef:
    return ContentRef(
        pack_id="fixture.presentation_mapper",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=digest_char * 64,
    )


def _binding(
    *,
    definition_ref: ContentRef,
    owner_uuid: UUID,
    provided_by_ref: ContentRef | None = None,
    origin_root_ref: ContentRef | None = None,
) -> BehaviorBinding:
    return BehaviorBinding(
        definition_ref=definition_ref,
        provided_by_ref=provided_by_ref or definition_ref,
        origin_root_ref=origin_root_ref,
        runtime_owner_uuid=owner_uuid,
    )


def _perspective(
    observer_uuid: UUID,
    *,
    controlled: bool = True,
) -> SubjectivePerspective:
    observer = str(observer_uuid)
    return SubjectivePerspective(
        perspective_epoch_id=f"epoch-{observer}",
        kind=(
            PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION
            if controlled
            else PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION
        ),
        controlled_entity_uuids=(observer,) if controlled else (),
        observer_entity_uuids=(observer,),
        active_observer_uuid=observer,
    )


def _context(
    perspective: SubjectivePerspective,
    *,
    source_cursor: int = 0,
    observation_cursor: int = 0,
    presentation_cursor: int = 0,
) -> SubjectiveFrameProjectionContext:
    return SubjectiveFrameProjectionContext(
        protocol=PlayerReplicationProtocolIdentity(
            source_stream_id="game-test",
            generation_id="generation-test",
        ),
        perspective=perspective,
        previous_watermarks=PlayerReplicationWatermarks(
            source_event_cursor=source_cursor,
            observation_cursor=observation_cursor,
            presentation_cursor=presentation_cursor,
            combat_log_cursor=0,
        ),
        next_observation_cursor=observation_cursor + 1,
    )


def _visible(
    event: _EventT,
    observer_uuid: UUID,
    *,
    identified: tuple[UUID, ...],
    located: tuple[UUID, ...] = (),
) -> _EventT:
    observer = str(observer_uuid)
    return event.model_copy(
        update={
            "identified_entity_observer_uuids": {
                str(entity_uuid): {observer} for entity_uuid in identified
            },
            "located_entity_observer_uuids": {
                str(entity_uuid): {observer} for entity_uuid in located
            },
        }
    )


def _batch(
    *events: Event,
    patches=(),
) -> CausalEventBatch:
    slots = tuple(
        ProjectedEventSlot(source_event_cursor=index, event=event)
        for index, event in enumerate(events, start=1)
    )
    return CausalEventBatch(
        slots=slots,
        through_source_event_cursor=len(slots),
        patches=patches,
    )


def _project_event_queue_since(
    source_cursor: int,
    perspective: SubjectivePerspective,
) -> tuple[SubjectiveReplicationFrame, tuple[ProjectedEventSlot, ...]]:
    slots = tuple(
        ProjectedEventSlot(source_event_cursor=cursor + 1, event=event)
        for cursor, event in EventQueue.iter_events_since(source_cursor)
    )
    return (
        MAPPER.project_frame(
            CausalEventBatch(
                slots=slots,
                through_source_event_cursor=EventQueue.event_cursor(),
            ),
            _context(perspective, source_cursor=source_cursor),
        ),
        slots,
    )


def _damage(
    *,
    source_uuid: UUID,
    target_uuid: UUID,
    parent_lineage: UUID,
    amount: int = 4,
    resulting_hp: int = 6,
    damage_type: DamageType = DamageType.FIRE,
) -> DamageAppliedEvent:
    component = Damage(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        damage_dice=4,
        dice_numbers=1,
        damage_type=damage_type,
        use_register=False,
    )
    return DamageAppliedEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        applied_damage=amount,
        normal_hit_point_damage=amount,
        temporary_hit_point_damage=0,
        resulting_normal_hp=resulting_hp,
        resulting_temporary_hp=0,
        damage_type=damage_type,
        damages=[component],
        parent_lineage=parent_lineage,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )


def _assert_closed_graph(frame) -> None:
    by_id = {cue.presentation_id: cue for cue in frame.presentation}
    assert len(by_id) == len(frame.presentation)
    for cue in frame.presentation:
        if cue.parent_presentation_id is not None:
            parent = by_id[cue.parent_presentation_id]
            assert cue.presentation_id in parent.child_presentation_ids
            assert parent.presentation_cursor < cue.presentation_cursor
        for child_id in cue.child_presentation_ids:
            assert by_id[child_id].parent_presentation_id == cue.presentation_id


@dataclass(frozen=True)
class _ReactiveMovementProjection:
    """One real movement execution plus its exact projected source window."""

    frame: SubjectiveReplicationFrame
    root_event: MovementEvent | JumpEvent
    mover_uuid: UUID
    path: tuple[tuple[int, int], ...]
    reactor_uuid_by_path_index: dict[int, UUID]
    reaction_ref_by_path_index: dict[int, ContentRef]
    weapon_ref_by_path_index: dict[int, ContentRef]
    step_slot_by_path_index: dict[int, ProjectedEventSlot]
    attack_slots_by_path_index: dict[int, tuple[ProjectedEventSlot, ...]]


def _project_real_multi_reaction_movement(
    movement_kind: MovementKind,
) -> _ReactiveMovementProjection:
    """Execute one real Move or Jump with two visible, deterministic misses."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 12, 6)
    try:
        mover = create_goblin(
            name=f"{movement_kind.value.title()} Mover",
            position=(1, 2),
            faction="heroes",
        )
        if movement_kind is MovementKind.WALK:
            path = tuple((x, 2) for x in range(1, 8))
            reactor_specs = (((1, 1), 2), ((4, 1), 5))
        else:
            path = tuple((x, 2) for x in range(1, 5))
            reactor_specs = (((0, 2), 1), ((2, 1), 3))

        reactor_uuid_by_path_index: dict[int, UUID] = {}
        reaction_ref_by_path_index: dict[int, ContentRef] = {}
        weapon_ref_by_path_index: dict[int, ContentRef] = {}
        for reactor_number, (position, path_index) in enumerate(
            reactor_specs,
            start=1,
        ):
            reactor = create_skeleton(
                name=f"Reaction Watcher {reactor_number}",
                position=position,
                faction="monsters",
            )
            add_opportunity_attack_handler(reactor)
            force_attack_miss(reactor)
            reactor_uuid_by_path_index[path_index] = reactor.uuid
            reaction_handler = next(
                handler
                for handler in reactor.event_handlers.values()
                if handler.semantic_key == "reaction.opportunity_attack"
            )
            assert reaction_handler.behavior_binding is not None
            reaction_ref_by_path_index[path_index] = (
                reaction_handler.behavior_binding.definition_ref
            )
            weapon = reactor.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
            assert weapon is not None
            assert weapon.content_ref is not None
            weapon_ref_by_path_index[path_index] = weapon.content_ref

        Entity.update_all_entities_senses(max_distance=20)
        observer_key = str(mover.uuid)

        def grant_all_event_participants(event: Event) -> dict[str, set[str]]:
            return {
                str(participant_uuid): {observer_key}
                for participant_uuid in event.get_participant_entity_uuids()
            }

        EventQueue.set_identified_entity_observer_computer(
            grant_all_event_participants
        )
        source_cursor = EventQueue.event_cursor()
        root_event = (
            Move(
                source_entity_uuid=mover.uuid,
                end_position=path[-1],
                path=tuple(path),
            ).apply()
            if movement_kind is MovementKind.WALK
            else Jump(
                source_entity_uuid=mover.uuid,
                end_position=path[-1],
            ).apply()
        )
        assert isinstance(root_event, (MovementEvent, JumpEvent))

        slots = tuple(
            ProjectedEventSlot(source_event_cursor=index + 1, event=event)
            for index, event in EventQueue.iter_events_since(source_cursor)
        )
        batch = CausalEventBatch(
            slots=slots,
            through_source_event_cursor=EventQueue.event_cursor(),
        )
        frame = MAPPER.project_frame(
            batch,
            _context(_perspective(mover.uuid), source_cursor=source_cursor),
        )

        step_slot_by_path_index = {
            event.path_index: slot
            for slot in slots
            if isinstance((event := slot.event), StepMovementEvent)
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
            and event.committed
        }
        path_index_by_step_lineage = {
            slot.event.lineage_uuid: path_index
            for path_index, slot in step_slot_by_path_index.items()
        }
        attack_slots_by_path_index_lists: dict[
            int, list[ProjectedEventSlot]
        ] = {}
        for slot in slots:
            event = slot.event
            parent_lineage = event.parent_lineage
            if (
                not isinstance(event, AttackEvent)
                or event.phase is not EventPhase.COMPLETION
                or event.canceled
                or event.name != "Opportunity Attack"
                or parent_lineage is None
                or parent_lineage not in path_index_by_step_lineage
            ):
                continue
            path_index = path_index_by_step_lineage[parent_lineage]
            attack_slots_by_path_index_lists.setdefault(path_index, []).append(slot)

        return _ReactiveMovementProjection(
            frame=frame,
            root_event=root_event,
            mover_uuid=mover.uuid,
            path=path,
            reactor_uuid_by_path_index=reactor_uuid_by_path_index,
            reaction_ref_by_path_index=reaction_ref_by_path_index,
            weapon_ref_by_path_index=weapon_ref_by_path_index,
            step_slot_by_path_index=step_slot_by_path_index,
            attack_slots_by_path_index={
                path_index: tuple(attack_slots)
                for path_index, attack_slots in attack_slots_by_path_index_lists.items()
            },
        )
    finally:
        reset_combat_state()


def _assert_exact_reactive_movement_segments(
    projection: _ReactiveMovementProjection,
    *,
    movement_kind: MovementKind,
    expected_segments: tuple[
        tuple[int, tuple[tuple[int, int], ...]],
        ...,
    ],
) -> None:
    """Prove engine timing and the frame's exact pre-edge segment graph."""
    assert projection.root_event.phase is EventPhase.COMPLETION
    total_steps = len(projection.path) - 1
    assert tuple(sorted(projection.step_slot_by_path_index)) == tuple(
        range(1, total_steps + 1)
    )
    assert set(projection.attack_slots_by_path_index) == set(
        projection.reactor_uuid_by_path_index
    )

    for path_index, reactor_uuid in projection.reactor_uuid_by_path_index.items():
        step_slot = projection.step_slot_by_path_index[path_index]
        attack_slots = projection.attack_slots_by_path_index[path_index]
        assert len(attack_slots) == 1
        attack_slot = attack_slots[0]
        attack = attack_slot.event
        assert isinstance(attack, AttackEvent)
        assert attack.parent_lineage == step_slot.event.lineage_uuid
        assert attack.source_entity_uuid == reactor_uuid
        assert attack.target_entity_uuid == projection.mover_uuid
        assert attack.attack_outcome is AttackOutcome.MISS
        assert attack.behavior_binding is not None
        assert (
            attack.behavior_binding.definition_ref
            == projection.reaction_ref_by_path_index[path_index]
        )
        assert (
            attack.behavior_binding.provided_by_ref
            == projection.reaction_ref_by_path_index[path_index]
        )
        assert attack.source_item_uuid is not None
        assert attack.source_item_presentation is not None
        assert attack.source_item_presentation.content_ref is not None
        assert (
            ContentRef.model_validate(
                attack.source_item_presentation.content_ref.model_dump(
                    mode="python",
                ),
            )
            == projection.weapon_ref_by_path_index[path_index]
        )
        # Opportunity reactions finish while the Step EFFECT is dispatching;
        # the entity has not entered the destination until Step COMPLETION.
        assert attack_slot.source_event_cursor < step_slot.source_event_cursor

    semantic_cues = tuple(
        cue
        for cue in projection.frame.presentation
        if (
            isinstance(cue, MovementPresentationCue)
            and cue.entity_uuid == str(projection.mover_uuid)
        )
        or (
            isinstance(cue, AttackPresentationCue)
            and cue.target_uuid == str(projection.mover_uuid)
            and cue.action_name == "Opportunity Attack"
        )
    )
    movement_cues = tuple(
        cue for cue in semantic_cues if isinstance(cue, MovementPresentationCue)
    )
    attack_cues = tuple(
        cue for cue in semantic_cues if isinstance(cue, AttackPresentationCue)
    )
    assert not any(
        isinstance(cue, ActionPresentationCue)
        for cue in projection.frame.presentation
    )

    assert tuple(
        (cue.path_start_index, cue.trajectory) for cue in movement_cues
    ) == expected_segments
    assert all(cue.movement_kind is movement_kind for cue in movement_cues)
    assert all(cue.path_total_steps == total_steps for cue in movement_cues)
    assert len(attack_cues) == len(projection.reactor_uuid_by_path_index)
    for path_index, reactor_uuid in projection.reactor_uuid_by_path_index.items():
        cue = next(cue for cue in attack_cues if cue.actor_uuid == str(reactor_uuid))
        behaviors = tuple(
            attribution
            for attribution in cue.content_attributions
            if isinstance(
                attribution,
                (
                    UnrootedBehaviorPresentationAttribution,
                    RootedBehaviorPresentationAttribution,
                ),
            )
        )
        assert behaviors == (
            UnrootedBehaviorPresentationAttribution(
                role=BehaviorPresentationRole.BEHAVIOR,
                definition_ref=projection.reaction_ref_by_path_index[path_index],
                provided_by_ref=projection.reaction_ref_by_path_index[path_index],
            ),
        )
        source_items = tuple(
            attribution
            for attribution in cue.content_attributions
            if isinstance(attribution, SourceItemPresentationAttribution)
        )
        assert source_items == (
            SourceItemPresentationAttribution(
                definition_ref=projection.weapon_ref_by_path_index[path_index],
            ),
        )

    reconstructed_path = [projection.path[0]]
    next_path_start = 0
    for cue in movement_cues:
        represented_steps = len(cue.trajectory) - 1
        assert cue.path_start_index == next_path_start
        assert cue.trajectory[0] == reconstructed_path[-1]
        reconstructed_path.extend(cue.trajectory[1:])
        next_path_start += represented_steps

        last_step_path_index = cue.path_start_index + represented_steps
        last_step_slot = projection.step_slot_by_path_index[last_step_path_index]
        assert cue.source_event_cursor == last_step_slot.source_event_cursor
        assert cue.source_event_uuid == str(last_step_slot.event.uuid)

    assert tuple(reconstructed_path) == projection.path
    assert next_path_start == total_steps

    expected_semantic_order: list[tuple[str, int | str]] = []
    movement_by_start = {
        cue.path_start_index: cue for cue in movement_cues
    }
    attack_by_source_event_uuid = {
        cue.source_event_uuid: cue for cue in attack_cues
    }
    reactive_segment_starts = {
        path_index - 1
        for path_index in projection.reactor_uuid_by_path_index
    }
    for path_start_index, _trajectory in expected_segments:
        cue = movement_by_start[path_start_index]
        expected_semantic_order.append(("movement", path_start_index))
        path_index = path_start_index + 1
        if path_start_index not in reactive_segment_starts:
            assert cue.child_presentation_ids == ()
            continue

        attack_slot = projection.attack_slots_by_path_index[path_index][0]
        attack_cue = attack_by_source_event_uuid[str(attack_slot.event.uuid)]
        step = projection.step_slot_by_path_index[path_index].event
        assert isinstance(step, StepMovementEvent)
        assert cue.path_start_index == step.path_index - 1
        assert cue.trajectory[:2] == (step.from_position, step.to_position)
        assert cue.child_presentation_ids == (attack_cue.presentation_id,)
        assert attack_cue.parent_presentation_id == cue.presentation_id
        assert attack_cue.presentation_cursor == cue.presentation_cursor + 1
        expected_semantic_order.append(("attack", attack_cue.actor_uuid))

    assert tuple(
        (
            ("movement", cue.path_start_index)
            if isinstance(cue, MovementPresentationCue)
            else ("attack", cue.actor_uuid)
        )
        for cue in semantic_cues
    ) == tuple(expected_semantic_order)
    _assert_closed_graph(projection.frame)
    round_tripped = SubjectiveReplicationFrame.model_validate_json(
        projection.frame.model_dump_json()
    )
    assert round_tripped == projection.frame


def test_hidden_action_source_is_not_leaked_but_visible_damage_survives() -> None:
    """A hidden semantic parent is removed and its safe effect becomes a root."""
    observer = uuid4()
    hidden_attacker = uuid4()
    visible_target = uuid4()
    perspective = _perspective(observer, controlled=False)
    attack = AttackEvent(
        source_entity_uuid=hidden_attacker,
        target_entity_uuid=visible_target,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.HIT,
        damage_types=[DamageType.SLASHING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    attack = _visible(attack, observer, identified=(visible_target,))
    damage = _damage(
        source_uuid=hidden_attacker,
        target_uuid=visible_target,
        parent_lineage=attack.lineage_uuid,
    )
    damage = _visible(damage, observer, identified=(visible_target,))

    frame = MAPPER.project_frame(_batch(attack, damage), _context(perspective))

    assert len(frame.presentation) == 1
    projected = frame.presentation[0]
    assert isinstance(projected, DamagePresentationCue)
    assert projected.source_uuid is None
    assert projected.target_uuid == str(visible_target)
    assert projected.parent_presentation_id is None
    assert frame.watermarks.source_event_cursor == 2
    _assert_closed_graph(frame)


def test_fully_hidden_batch_advances_only_source_and_observation_watermarks() -> None:
    """Hidden source slots remain a real transaction without leaking a payload."""
    observer = uuid4()
    event = AttackEvent(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.HIT,
        damage_types=[DamageType.SLASHING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    frame = MAPPER.project_frame(
        _batch(event),
        _context(_perspective(observer, controlled=False)),
    )

    assert frame.presentation == ()
    assert frame.presentation_from_cursor == 0
    assert frame.watermarks == PlayerReplicationWatermarks(
        source_event_cursor=1,
        observation_cursor=1,
        presentation_cursor=0,
        combat_log_cursor=0,
    )


def test_missed_attack_keeps_ordered_element_categories_without_damage_children() -> None:
    """Miss VFX dispatch uses attack-owned immutable damage types."""
    actor = uuid4()
    target = uuid4()
    action_ref = _content_ref(
        kind=ContentDefinitionKind.ACTION,
        content_id="action.longbow_attack",
        digest_char="a",
    )
    event = AttackEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        behavior_binding=_binding(
            definition_ref=action_ref,
            owner_uuid=actor,
        ),
        weapon_slot=WeaponSlot.RANGED_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.FIRE, DamageType.PIERCING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    event = _visible(event, actor, identified=(actor, target))

    frame = MAPPER.project_frame(
        _batch(event),
        _context(_perspective(actor)),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, AttackPresentationCue)
    assert cue.damage_types == (
        PresentationDamageType.FIRE,
        PresentationDamageType.PIERCING,
    )
    assert cue.impact_effect_presentation_ids == ()
    assert cue.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=action_ref,
            provided_by_ref=action_ref,
        ),
    )


def test_duplicate_spell_targets_keep_distinct_projection_applications() -> None:
    """Application lineage, not target UUID, attaches each ordered impact."""
    caster = uuid4()
    target = uuid4()
    perspective = _perspective(caster)
    root = SpellEvent(
        name="Magic Missile",
        spell_id="magic_missile",
        source_entity_uuid=caster,
        target_entity_uuid=target,
        spell_school="evocation",
        spell_level=1,
        cast_at_level=1,
        range_type="ranged",
        projectile_type="dart",
        total_targets=2,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    root = _visible(root, caster, identified=(caster, target), located=(caster, target))
    application_events: list[SpellEvent] = []
    damages: list[DamageAppliedEvent] = []
    for application_index in range(2):
        application = SpellEvent(
            name="Magic Missile",
            spell_id="magic_missile",
            source_entity_uuid=caster,
            target_entity_uuid=target,
            spell_school="evocation",
            spell_level=1,
            cast_at_level=1,
            range_type="ranged",
            projectile_type="dart",
            application_index=application_index,
            application_id=uuid4(),
            parent_lineage=root.lineage_uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        application = _visible(
            application,
            caster,
            identified=(caster, target),
            located=(caster, target),
        )
        damage = _damage(
            source_uuid=caster,
            target_uuid=target,
            parent_lineage=application.lineage_uuid,
            amount=3,
            resulting_hp=10 - ((application_index + 1) * 3),
            damage_type=DamageType.FORCE,
        )
        damage = _visible(damage, caster, identified=(caster, target))
        application_events.append(application)
        damages.append(damage)

    frame = MAPPER.project_frame(
        _batch(root, application_events[0], damages[0], application_events[1], damages[1]),
        _context(perspective),
    )

    spell = frame.presentation[0]
    assert isinstance(spell, SpellPresentationCue)
    assert spell.spell_id == "magic_missile"
    assert spell.delivery is SpellDelivery.MISSILE_VOLLEY
    assert spell.projectile_type is PresentationProjectile.DART
    assert [application.application_index for application in spell.targets] == [0, 1]
    assert [application.target_uuid for application in spell.targets] == [str(target)] * 2
    assert len({application.application_id for application in spell.targets}) == 2
    assert all(len(application.effect_presentation_ids) == 1 for application in spell.targets)
    assert spell.child_presentation_ids == tuple(
        effect_id
        for application in spell.targets
        for effect_id in application.effect_presentation_ids
    )
    _assert_closed_graph(frame)


def test_spell_created_spatial_effect_is_an_exact_position_application() -> None:
    """A visible world-effect lifecycle stays causally owned by its spell."""
    observer = uuid4()
    caster = uuid4()
    effect_uuid = uuid4()
    position = (7, 9)
    spell_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.grease",
        digest_char="e",
    )
    effect_ref = _content_ref(
        kind=ContentDefinitionKind.SPATIAL_EFFECT,
        content_id="spatial_effect.grease",
        digest_char="f",
    )
    spell = SpellEvent(
        name="Grease",
        spell_id="grease",
        source_entity_uuid=caster,
        spell_school="conjuration",
        spell_level=1,
        cast_at_level=1,
        range_type="ranged",
        behavior_binding=_binding(
            definition_ref=spell_ref,
            owner_uuid=caster,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    spell = _visible(spell, observer, identified=(caster,), located=(caster,))
    lifecycle = SpatialEffectChangeEvent(
        source_entity_uuid=caster,
        parent_event=spell.uuid,
        operation=SpatialEffectChangeOperation.CREATED,
        spatial_effect_uuid=effect_uuid,
        spatial_effect_content_ref=effect_ref,
        spatial_effect_name="Grease",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        anchor_position=position,
        affected_positions=(position, (8, 9)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    ).model_copy(
        update={
            "located_position_observer_uuids": {
                position_evidence_key(position): {str(observer)},
                position_evidence_key((8, 9)): {str(observer)},
            },
        },
    )

    frame = MAPPER.project_frame(
        _batch(spell, lifecycle),
        _context(_perspective(observer, controlled=False)),
    )

    assert len(frame.presentation) == 2
    spell_cue, effect_cue = frame.presentation
    assert isinstance(spell_cue, SpellPresentationCue)
    assert isinstance(effect_cue, SpatialEffectPresentationCue)
    assert spell_cue.child_presentation_ids == (effect_cue.presentation_id,)
    assert effect_cue.parent_presentation_id == spell_cue.presentation_id
    assert effect_cue.effect_uuid == str(effect_uuid)
    assert effect_cue.content_ref == effect_ref
    assert effect_cue.operation is SpatialEffectChangeOperation.CREATED
    assert effect_cue.affected_positions == (position, (8, 9))
    assert spell_cue.targets == (
        SpellTargetPresentation(
            application_index=0,
            application_id=f"{spell_cue.presentation_id}:application:0",
            outcome=SpellApplicationOutcome.AUTOMATIC,
            position=position,
            effect_presentation_ids=(effect_cue.presentation_id,),
        ),
    )
    _assert_closed_graph(frame)


def test_spatial_effect_lifecycle_does_not_disclose_unobserved_geometry() -> None:
    """Exact content and coordinates are omitted without event-time cell grants."""
    observer = uuid4()
    caster = uuid4()
    position = (70, 90)
    effect_ref = _content_ref(
        kind=ContentDefinitionKind.SPATIAL_EFFECT,
        content_id="spatial_effect.hidden",
        digest_char="9",
    )
    lifecycle = SpatialEffectChangeEvent(
        source_entity_uuid=caster,
        operation=SpatialEffectChangeOperation.CREATED,
        spatial_effect_uuid=uuid4(),
        spatial_effect_content_ref=effect_ref,
        spatial_effect_name="Hidden Effect",
        layer=SpatialEffectLayer.FIELD,
        anchor_position=position,
        affected_positions=(position,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    frame = MAPPER.project_frame(
        _batch(lifecycle),
        _context(_perspective(observer, controlled=False)),
    )

    assert frame.presentation == ()
    assert effect_ref.identity_key not in frame.model_dump_json()
    assert frame.watermarks.source_event_cursor == 1


def test_drink_uses_frozen_item_state_after_registry_loss() -> None:
    """No item or action registry lookup is needed after a consumable disappears."""
    actor = uuid4()
    item_uuid = uuid4()
    perspective = _perspective(actor)
    item_ref = _content_ref(
        kind=ContentDefinitionKind.ITEM,
        content_id="item.healing_potion.crimson",
        digest_char="b",
    )
    action_ref = _content_ref(
        kind=ContentDefinitionKind.ACTION,
        content_id="action.drink_potion",
        digest_char="c",
    )
    snapshot = ItemPresentationState(
        item_uuid=item_uuid,
        content_ref=ItemContentRefSnapshot.model_validate(
            item_ref.model_dump(mode="python")
        ),
        semantic_key="healing_potion",
        name="Potion of Healing",
        item_kind=ItemPresentationKind.USABLE,
        rarity=ItemRarity.COMMON,
        weight=0.5,
        visual_item_name="Potion of Healing",
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        charges=1,
        max_charges=1,
        stack_count=1,
        max_stack=10,
        is_consumable=True,
    )
    action = ActionEvent(
        name="Drink Potion",
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        source_item_uuid=item_uuid,
        source_item_presentation=snapshot,
        behavior_binding=_binding(
            definition_ref=action_ref,
            provided_by_ref=item_ref,
            origin_root_ref=item_ref,
            owner_uuid=item_uuid,
        ),
        presentation_kind=ActionPresentationKind.DRINK,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    heal = HealEvent(
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        actual_healing=7,
        total_healing=7,
        resulting_hp=12,
        resulting_normal_hp=12,
        resulting_temporary_hp=0,
        parent_lineage=action.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    frame = MAPPER.project_frame(_batch(action, heal), _context(perspective))

    item = frame.presentation[0]
    assert isinstance(item, ItemActionPresentationCue)
    assert item.item_uuid == str(item_uuid)
    assert item.item_kind is ItemPresentationKind.USABLE
    assert isinstance(frame.presentation[1], HealPresentationCue)
    assert item.effect_presentation_ids == (frame.presentation[1].presentation_id,)
    assert item.content_attributions == (
        RootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=action_ref,
            provided_by_ref=item_ref,
            origin_root_ref=item_ref,
        ),
        SourceItemPresentationAttribution(definition_ref=item_ref),
    )
    _assert_closed_graph(frame)


def test_condition_cue_projects_exact_bound_definition_without_name_inference() -> None:
    """Condition display labels remain separate from authenticated identity."""
    actor = uuid4()
    target = uuid4()
    condition_ref = _content_ref(
        kind=ContentDefinitionKind.CONDITION,
        content_id="condition.prone",
        digest_char="d",
    )
    condition = Prone(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        behavior_binding=_binding(
            definition_ref=condition_ref,
            owner_uuid=target,
        ),
        use_register=False,
    )
    event = ConditionApplicationEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        condition=condition,
        condition_content_identity=condition_ref.identity_key,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    event = _visible(event, actor, identified=(target,))

    frame = MAPPER.project_frame(
        _batch(event),
        _context(_perspective(actor)),
    )

    cue = frame.presentation[0]
    assert cue.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=condition_ref,
            provided_by_ref=condition_ref,
        ),
    )


@pytest.mark.parametrize(
    ("definition_kind", "content_id"),
    (
        (ContentDefinitionKind.ACTION, "action.rage"),
        (ContentDefinitionKind.REACTION, "reaction.defensive_flare"),
    ),
)
def test_generic_action_preserves_existing_condition_causality(
    definition_kind: ContentDefinitionKind,
    content_id: str,
) -> None:
    """The mapper delivers the authored parent instead of orphaning its effect."""

    actor = uuid4()
    action_ref = _content_ref(
        kind=definition_kind,
        content_id=content_id,
        digest_char="e",
    )
    condition_ref = _content_ref(
        kind=ContentDefinitionKind.CLASS_FEATURE,
        content_id="feature.raging",
        digest_char="f",
    )
    action = ActionEvent(
        name="Rage",
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        behavior_binding=_binding(
            definition_ref=action_ref,
            owner_uuid=actor,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    condition = ConditionApplicationEvent(
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        condition=Prone(
            source_entity_uuid=actor,
            target_entity_uuid=actor,
            behavior_binding=_binding(
                definition_ref=condition_ref,
                owner_uuid=actor,
            ),
            use_register=False,
        ),
        condition_content_identity=condition_ref.identity_key,
        parent_lineage=action.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    action = _visible(action, actor, identified=(actor,))
    condition = _visible(condition, actor, identified=(actor,))

    frame = MAPPER.project_frame(
        _batch(action, condition),
        _context(_perspective(actor)),
    )

    root, effect = frame.presentation
    assert isinstance(root, ActionPresentationCue)
    assert root.actor_uuid == str(actor)
    assert root.action_name == "Rage"
    assert root.target_uuids == (str(actor),)
    assert root.effect_presentation_ids == (effect.presentation_id,)
    assert root.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=action_ref,
            provided_by_ref=action_ref,
        ),
    )
    assert effect.parent_presentation_id == root.presentation_id
    assert effect.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=condition_ref,
            provided_by_ref=condition_ref,
        ),
    )
    _assert_closed_graph(frame)


def test_generic_action_derives_safe_targets_from_typed_child_actions() -> None:
    """A composite action owns its visible attack without trusting hidden target state."""

    actor = uuid4()
    target = uuid4()
    action_ref = _content_ref(
        kind=ContentDefinitionKind.ACTION,
        content_id="action.monster.multiattack",
        digest_char="a",
    )
    attack_ref = _content_ref(
        kind=ContentDefinitionKind.ACTION,
        content_id="action.attack",
        digest_char="b",
    )
    action = ActionEvent(
        name="Multiattack",
        source_entity_uuid=actor,
        behavior_binding=_binding(
            definition_ref=action_ref,
            owner_uuid=actor,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    attack = AttackEvent(
        name="Claw",
        source_entity_uuid=actor,
        target_entity_uuid=target,
        behavior_binding=_binding(
            definition_ref=attack_ref,
            owner_uuid=actor,
        ),
        parent_lineage=action.lineage_uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    action = _visible(action, actor, identified=(actor,))
    attack = _visible(attack, actor, identified=(actor, target))

    frame = MAPPER.project_frame(
        _batch(action, attack),
        _context(_perspective(actor)),
    )

    root, child = frame.presentation
    assert isinstance(root, ActionPresentationCue)
    assert isinstance(child, AttackPresentationCue)
    assert root.target_uuids == (str(target),)
    assert root.effect_presentation_ids == (child.presentation_id,)
    assert child.parent_presentation_id == root.presentation_id
    _assert_closed_graph(frame)


def test_handler_only_shield_reaction_owns_its_emitted_condition() -> None:
    """Shield gets an exact action root instead of borrowing the incoming attack."""

    defender = uuid4()
    attacker = uuid4()
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.spell.shield",
        digest_char="c",
    )
    attack_ref = _content_ref(
        kind=ContentDefinitionKind.ACTION,
        content_id="action.attack",
        digest_char="d",
    )
    condition_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.shield",
        digest_char="e",
    )
    incoming = AttackEvent(
        name="Incoming Attack",
        source_entity_uuid=attacker,
        target_entity_uuid=defender,
        behavior_binding=_binding(
            definition_ref=attack_ref,
            owner_uuid=attacker,
        ),
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    condition = ConditionApplicationEvent(
        source_entity_uuid=defender,
        target_entity_uuid=defender,
        condition=Prone(
            source_entity_uuid=defender,
            target_entity_uuid=defender,
            behavior_binding=_binding(
                definition_ref=condition_ref,
                owner_uuid=defender,
            ),
            use_register=False,
        ),
        condition_content_identity=condition_ref.identity_key,
        parent_lineage=incoming.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    incoming = _visible(
        incoming,
        defender,
        identified=(attacker, defender),
    )
    condition = _visible(
        condition,
        defender,
        identified=(defender,),
    )
    incoming._effective_handler_presentations = (
        EffectiveHandlerPresentation(
            dispatch_index=1,
            handler_name="Shield",
            behavior_binding=_binding(
                definition_ref=reaction_ref,
                owner_uuid=defender,
            ),
            source_entity_uuid=defender,
            triggering_event_uuid=incoming.uuid,
            triggering_lineage_uuid=incoming.lineage_uuid,
            emitted_lineage_uuids=(condition.lineage_uuid,),
            outcome=HandlerDispatchOutcome.MODIFIED_EVENT,
        ),
    )

    frame = MAPPER.project_frame(
        _batch(incoming, condition),
        _context(_perspective(defender)),
    )

    reaction = next(
        cue for cue in frame.presentation
        if isinstance(cue, ActionPresentationCue)
    )
    attack = next(
        cue for cue in frame.presentation
        if isinstance(cue, AttackPresentationCue)
    )
    effect = next(
        cue for cue in frame.presentation
        if isinstance(cue, ConditionPresentationCue)
    )
    assert isinstance(reaction, ActionPresentationCue)
    assert reaction.action_name == "Shield"
    assert reaction.actor_uuid == str(defender)
    assert reaction.target_uuids == (str(defender),)
    assert reaction.effect_presentation_ids == (effect.presentation_id,)
    assert isinstance(attack, AttackPresentationCue)
    assert attack.parent_presentation_id is None
    assert effect.parent_presentation_id == reaction.presentation_id
    assert reaction.presentation_cursor < effect.presentation_cursor
    assert effect.presentation_cursor < attack.presentation_cursor
    assert reaction.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=reaction_ref,
            provided_by_ref=reaction_ref,
        ),
    )
    _assert_closed_graph(frame)


def test_real_shield_handler_reaches_the_canonical_action_root() -> None:
    """The production handler bridge preserves Shield without synthetic events."""

    reset_combat_state()
    get_map().create_rectangle(0, 0, 6, 6)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        defender = Entity.create(
            source_entity_uuid=uuid4(),
            name="Shield Defender",
            config=EntityConfig(
                action_economy=ActionEconomyConfig(spell_slots={1: 1}),
                position=(2, 2),
                faction="heroes",
            ),
        )
        attacker = create_goblin(
            name="Shield Attacker",
            position=(2, 3),
            faction="monsters",
        )
        handler = create_shield_reaction_handler(defender.uuid)
        defender.add_event_handler(handler)
        assert handler.behavior_binding is not None
        Entity.update_all_entities_senses(max_distance=20)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {str(defender.uuid)}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        before = EventQueue.event_cursor()
        attack_action = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
        attack_ref = get_content_declaration(Attack).ref
        attack_action.behavior_binding = _binding(
            definition_ref=attack_ref,
            owner_uuid=attacker.uuid,
        )
        with fixed_dice_faces(10):
            result = attack_action.apply()
        assert isinstance(result, AttackEvent)
        assert result.attack_outcome is AttackOutcome.MISS

        source_events = tuple(
            event
            for _, event in EventQueue.iter_events_since(before)
        )
        frame = MAPPER.project_frame(
            _batch(*source_events),
            _context(_perspective(defender.uuid)),
        )

        shield = next(
            cue
            for cue in frame.presentation
            if (
                isinstance(cue, ActionPresentationCue)
                and cue.content_attributions
                and cue.content_attributions[0].definition_ref
                == handler.behavior_binding.definition_ref
            )
        )
        incoming = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, AttackPresentationCue)
        )
        shield_effects = [
            cue
            for cue in frame.presentation
            if cue.parent_presentation_id == shield.presentation_id
        ]
        assert shield.action_name == "Shield"
        assert shield.actor_uuid == str(defender.uuid)
        assert shield.target_uuids == (str(defender.uuid),)
        assert shield.trigger_presentation_id == incoming.presentation_id
        assert len(shield_effects) == 1
        assert isinstance(shield_effects[0], ConditionPresentationCue)
        assert incoming.parent_presentation_id is None
        assert shield.presentation_cursor < shield_effects[0].presentation_cursor
        assert shield_effects[0].presentation_cursor < incoming.presentation_cursor
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_real_parry_handler_uses_public_reaction_identity_for_action_root() -> None:
    """Parry activation must not expose its persistent trait as an action root."""

    reset_combat_state()
    get_map().create_rectangle(0, 0, 6, 6)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        defender = create_goblin(
            name="Parry Defender",
            position=(2, 2),
            faction="heroes",
        )
        attacker = create_goblin(
            name="Parry Attacker",
            position=(2, 3),
            faction="monsters",
        )
        defender.add_condition(
            ParryFeature(
                source_entity_uuid=defender.uuid,
                target_entity_uuid=defender.uuid,
            ),
        )
        handler = next(
            candidate
            for candidate in defender.event_handlers.values()
            if candidate.name == "Parry"
        )
        assert handler.behavior_binding is not None
        assert (
            handler.behavior_binding.definition_ref.definition_kind
            is ContentDefinitionKind.REACTION
        )
        assert (
            handler.behavior_binding.definition_ref.content_id
            == "reaction.monster.parry"
        )
        assert (
            handler.behavior_binding.provided_by_ref
            == get_content_declaration(ParryFeature).ref
        )
        Entity.update_all_entities_senses(max_distance=20)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {str(defender.uuid)}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        before = EventQueue.event_cursor()
        attack_action = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
        attack_action.behavior_binding = _binding(
            definition_ref=get_content_declaration(Attack).ref,
            owner_uuid=attacker.uuid,
        )
        attack_bonus = attacker.attack_bonus(
            WeaponSlot.MELEE_MAIN,
            defender.uuid,
        ).normalized_score
        armor_class = defender.ac_bonus(attacker.uuid).normalized_score
        marginal_face = armor_class - attack_bonus
        assert 2 <= marginal_face <= 19
        with fixed_dice_faces(marginal_face):
            result = attack_action.apply()
        assert isinstance(result, AttackEvent)
        assert result.attack_outcome is AttackOutcome.MISS

        source_events = tuple(
            event
            for _, event in EventQueue.iter_events_since(before)
        )
        frame = MAPPER.project_frame(
            _batch(*source_events),
            _context(_perspective(defender.uuid)),
        )

        parry = next(
            cue
            for cue in frame.presentation
            if (
                isinstance(cue, ActionPresentationCue)
                and cue.content_attributions
                and cue.content_attributions[0].definition_ref
                == handler.behavior_binding.definition_ref
            )
        )
        incoming = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, AttackPresentationCue)
        )
        assert parry.action_name == "Parry"
        assert parry.actor_uuid == str(defender.uuid)
        assert parry.target_uuids == (str(defender.uuid),)
        assert parry.trigger_presentation_id == incoming.presentation_id
        assert parry.effect_presentation_ids == ()
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_handler_only_divine_smite_reaction_gets_an_exact_root() -> None:
    """A modifying reaction with no emitted child remains an authored action cue."""

    paladin = uuid4()
    target = uuid4()
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.class_feature.paladin.divine_smite",
        digest_char="f",
    )
    trigger = Event(
        name="Damage Roll Result",
        event_type=EventType.DAMAGE_ROLL_RESULT,
        source_entity_uuid=paladin,
        target_entity_uuid=target,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    trigger = _visible(
        trigger,
        paladin,
        identified=(paladin, target),
    )
    trigger._effective_handler_presentations = (
        EffectiveHandlerPresentation(
            dispatch_index=2,
            handler_name="Divine Smite (L3)",
            behavior_binding=_binding(
                definition_ref=reaction_ref,
                owner_uuid=paladin,
            ),
            source_entity_uuid=paladin,
            triggering_event_uuid=trigger.uuid,
            triggering_lineage_uuid=trigger.lineage_uuid,
            emitted_lineage_uuids=(),
            outcome=HandlerDispatchOutcome.MODIFIED_EVENT,
        ),
    )

    frame = MAPPER.project_frame(
        _batch(trigger),
        _context(_perspective(paladin)),
    )

    assert len(frame.presentation) == 1
    reaction = frame.presentation[0]
    assert isinstance(reaction, ActionPresentationCue)
    assert reaction.action_name == "Divine Smite (L3)"
    assert reaction.actor_uuid == str(paladin)
    assert reaction.target_uuids == (str(target),)
    assert reaction.effect_presentation_ids == ()
    assert reaction.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=reaction_ref,
            provided_by_ref=reaction_ref,
        ),
    )
    _assert_closed_graph(frame)


def test_emission_only_handler_without_a_delivered_result_is_suppressed() -> None:
    """Canceled/hidden emissions cannot become empty generic reaction actions."""

    reactor = uuid4()
    target = uuid4()
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.opportunity_attack",
        digest_char="e",
    )
    trigger = Event(
        name="Movement Trigger",
        event_type=EventType.STEP_MOVEMENT,
        source_entity_uuid=target,
        target_entity_uuid=target,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    trigger = _visible(
        trigger,
        target,
        identified=(reactor, target),
    )
    trigger._effective_handler_presentations = (
        EffectiveHandlerPresentation(
            dispatch_index=3,
            handler_name="Opportunity Attack Handler",
            behavior_binding=_binding(
                definition_ref=reaction_ref,
                owner_uuid=reactor,
            ),
            source_entity_uuid=reactor,
            triggering_event_uuid=trigger.uuid,
            triggering_lineage_uuid=trigger.lineage_uuid,
            emitted_lineage_uuids=(uuid4(),),
            outcome=HandlerDispatchOutcome.EMITTED_EVENTS,
        ),
    )

    frame = MAPPER.project_frame(
        _batch(trigger),
        _context(_perspective(target)),
    )

    assert frame.presentation == ()


def test_real_divine_smite_handler_reaches_the_canonical_action_root() -> None:
    """The production smite handler exposes activation before the attack impact."""

    reset_combat_state()
    get_map().create_rectangle(0, 0, 6, 6)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        paladin = create_goblin(
            name="Smite Attacker",
            position=(2, 2),
            faction="heroes",
        )
        target = create_skeleton(
            name="Smite Target",
            position=(2, 3),
            faction="monsters",
        )
        target.health.damage_reduction.self_static.add_resistance_modifier(
            ResistanceModifier(
                source_entity_uuid=target.uuid,
                target_entity_uuid=target.uuid,
                name="Smite packet slashing resistance",
                value=ResistanceStatus.RESISTANCE,
                damage_type=DamageType.SLASHING,
            ),
        )
        slot_base = paladin.action_economy.spell_slot_1.get_base_modifier()
        assert slot_base is not None
        slot_base.value = 1
        handler = create_divine_smite_handler(paladin.uuid, 1)
        paladin.add_event_handler(handler)
        assert handler.behavior_binding is not None
        Entity.update_all_entities_senses(max_distance=20)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {str(paladin.uuid)}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        before = EventQueue.event_cursor()
        attack_action = Attack(
            source_entity_uuid=paladin.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
        attack_action.behavior_binding = _binding(
            definition_ref=get_content_declaration(Attack).ref,
            owner_uuid=paladin.uuid,
        )
        with fixed_dice_faces(20, *([4] * 10)):
            result = attack_action.apply()
        assert isinstance(result, AttackEvent)
        assert result.attack_outcome is AttackOutcome.CRIT

        source_events = tuple(
            event
            for _, event in EventQueue.iter_events_since(before)
        )
        damage_result = next(
            event
            for event in source_events
            if (
                isinstance(event, DamageRollResultEvent)
                and event.phase is EventPhase.COMPLETION
            )
        )
        assert len(damage_result.damage_packets) == 2
        assert (
            damage_result.damage_packets[1].damage.damage_type
            is DamageType.RADIANT
        )
        assert damage_result.roll_modifications[-1].operation is (
            RollModificationOperation.APPEND
        )
        assert damage_result.roll_modifications[-1].handler_name == "Divine Smite"
        assert damage_result.roll_modifications[-1].packet_index == 1
        frame = MAPPER.project_frame(
            _batch(*source_events),
            _context(_perspective(paladin.uuid)),
        )

        smite = next(
            cue
            for cue in frame.presentation
            if (
                isinstance(cue, ActionPresentationCue)
                and cue.content_attributions
                and cue.content_attributions[0].definition_ref
                == handler.behavior_binding.definition_ref
            )
        )
        attack = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, AttackPresentationCue)
        )
        impact = next(
            cue
            for cue in frame.presentation
            if (
                isinstance(cue, DamagePresentationCue)
                and cue.parent_presentation_id == attack.presentation_id
            )
        )
        assert smite.action_name == "Divine Smite (L1)"
        assert smite.actor_uuid == str(paladin.uuid)
        assert smite.target_uuids == (str(target.uuid),)
        assert smite.trigger_presentation_id == attack.presentation_id
        assert smite.effect_presentation_ids == ()
        assert impact.applied_amount == 29
        assert PresentationDamageType.RADIANT in impact.damage_types
        assert smite.presentation_cursor < attack.presentation_cursor
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


@pytest.mark.parametrize(
    ("automatic", "succeeded", "incoming_level", "slot_level", "total", "dc", "resolution_type"),
    (
        (True, True, 3, 3, None, None, CounterspellAutomaticSuccess),
        (False, False, 5, 3, 14, 15, CounterspellCheckFailure),
    ),
)
def test_counterspell_maps_closed_reaction_and_trigger_identity(
    automatic: bool,
    succeeded: bool,
    incoming_level: int,
    slot_level: int,
    total: int | None,
    dc: int | None,
    resolution_type: type[CounterspellAutomaticSuccess] | type[CounterspellCheckFailure],
) -> None:
    """Counterspell survives without exposing an engine event or name-derived key."""
    caster = uuid4()
    reactor = uuid4()
    spell_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.fireball",
        digest_char="e",
    )
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.spell.counterspell",
        digest_char="f",
    )
    incoming = SpellEvent(
        name="Display Name May Change",
        spell_id="fireball",
        source_entity_uuid=caster,
        target_entity_uuid=reactor,
        spell_school="evocation",
        spell_level=incoming_level,
        cast_at_level=incoming_level,
        range_type="ranged",
        behavior_binding=_binding(
            definition_ref=spell_ref,
            owner_uuid=caster,
        ),
        phase=EventPhase.EXECUTION,
        use_register=False,
    )
    reaction = CounterspellReactionEvent(
        source_entity_uuid=reactor,
        target_entity_uuid=caster,
        triggered_event_uuid=incoming.uuid,
        triggered_lineage_uuid=incoming.lineage_uuid,
        incoming_spell_name=incoming.name,
        incoming_spell_level=incoming_level,
        counterspell_slot_level=slot_level,
        automatic=automatic,
        check_total=total,
        check_dc=dc,
        succeeded=succeeded,
        outcome_code=(
            COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
            if succeeded
            else COUNTERSPELL_FAILURE_OUTCOME_CODE
        ),
        reaction_content_identity=reaction_ref.identity_key,
        incoming_spell_content_identity=spell_ref.identity_key,
        behavior_binding=_binding(
            definition_ref=reaction_ref,
            owner_uuid=reactor,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(
        reaction,
        caster,
        identified=(caster, reactor),
    )
    reaction._effective_handler_presentations = (
        EffectiveHandlerPresentation(
            dispatch_index=3,
            handler_name="Counterspell",
            behavior_binding=_binding(
                definition_ref=reaction_ref,
                owner_uuid=reactor,
            ),
            source_entity_uuid=reactor,
            triggering_event_uuid=incoming.uuid,
            triggering_lineage_uuid=incoming.lineage_uuid,
            emitted_lineage_uuids=(reaction.lineage_uuid,),
            outcome=HandlerDispatchOutcome.EMITTED_EVENTS,
        ),
    )

    frame = MAPPER.project_frame(
        _batch(incoming, reaction),
        _context(_perspective(caster)),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, CounterspellPresentationCue)
    assert cue.reactor_uuid == str(reactor)
    assert cue.incoming_caster_uuid == str(caster)
    assert isinstance(cue.resolution, resolution_type)
    assert cue.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=reaction_ref,
            provided_by_ref=reaction_ref,
        ),
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.TRIGGER_BEHAVIOR,
            definition_ref=spell_ref,
            provided_by_ref=spell_ref,
        ),
    )
    assert "event" not in cue.model_dump()


def test_counterspell_with_hidden_reactor_fails_closed() -> None:
    """An identified incoming caster never implies identity of the reactor."""
    caster = uuid4()
    reactor = uuid4()
    spell_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.fireball",
        digest_char="1",
    )
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.spell.counterspell",
        digest_char="2",
    )
    incoming = SpellEvent(
        name="Fireball",
        spell_id="fireball",
        source_entity_uuid=caster,
        target_entity_uuid=reactor,
        spell_school="evocation",
        spell_level=3,
        cast_at_level=3,
        range_type="ranged",
        behavior_binding=_binding(
            definition_ref=spell_ref,
            owner_uuid=caster,
        ),
        phase=EventPhase.EXECUTION,
        use_register=False,
    )
    reaction = CounterspellReactionEvent(
        source_entity_uuid=reactor,
        target_entity_uuid=caster,
        triggered_event_uuid=incoming.uuid,
        triggered_lineage_uuid=incoming.lineage_uuid,
        incoming_spell_name=incoming.name,
        incoming_spell_level=3,
        counterspell_slot_level=3,
        automatic=True,
        succeeded=True,
        outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
        reaction_content_identity=reaction_ref.identity_key,
        incoming_spell_content_identity=spell_ref.identity_key,
        behavior_binding=_binding(
            definition_ref=reaction_ref,
            owner_uuid=reactor,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(reaction, caster, identified=(caster,))

    frame = MAPPER.project_frame(
        _batch(incoming, reaction),
        _context(_perspective(caster)),
    )

    assert frame.presentation == ()


def test_shove_owns_its_exact_forced_movement_child() -> None:
    """Shove contact preserves actor, target, cause, path, and child timing."""
    actor = uuid4()
    target = uuid4()
    perspective = _perspective(actor)
    shove = ShoveEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        contest_success=True,
        push_distance=10,
        end_position=(4, 1),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    shove = _visible(shove, actor, identified=(actor, target), located=(actor, target))
    forced = ForcedMovementEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        start_position=(2, 1),
        end_position=(4, 1),
        direction=(1, 0),
        intended_distance=10,
        actual_distance=10,
        cause="shove",
        parent_lineage=shove.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    forced = _visible(forced, actor, identified=(actor, target), located=(target,))

    frame = MAPPER.project_frame(_batch(shove, forced), _context(perspective))

    shove_cue, forced_cue = frame.presentation
    assert isinstance(shove_cue, ShovePresentationCue)
    assert isinstance(forced_cue, ForcedMovementPresentationCue)
    assert shove_cue.forced_movement_presentation_id == forced_cue.presentation_id
    assert forced_cue.cause is ForcedMovementCause.SHOVE
    assert forced_cue.actor_action_presentation_id == shove_cue.presentation_id
    assert forced_cue.start_position == (2, 1)
    assert forced_cue.end_position == (4, 1)
    _assert_closed_graph(frame)


@pytest.mark.parametrize("controlled", [False, True])
def test_real_shove_keeps_child_before_root_forced_movement(
    controlled: bool,
) -> None:
    """The real engine path preserves spectated and controlled shoves."""

    reset_combat_state()
    get_map().create_rectangle(0, 0, 8, 8)
    try:
        shover = create_goblin(
            name="Spectated Shove Hero",
            position=(2, 2),
            faction="heroes",
        )
        target = create_goblin(
            name="Spectated Shove Target",
            position=(3, 2),
            faction="monsters",
        )
        target.weight = 40
        Entity.update_all_entities_senses(max_distance=20)
        observer_key = str(shover.uuid)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {observer_key}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        source_cursor = EventQueue.event_cursor()
        with fixed_dice_faces(20):
            result = Shove(
                source_entity_uuid=shover.uuid,
                target_entity_uuid=target.uuid,
            ).apply()
        assert isinstance(result, ShoveEvent)
        assert result.contest_success is True
        assert result.push_distance > 0

        source_slots = tuple(
            ProjectedEventSlot(source_event_cursor=cursor + 1, event=event)
            for cursor, event in EventQueue.iter_events_since(source_cursor)
        )
        forced_completion_index = next(
            index
            for index, slot in enumerate(source_slots)
            if isinstance(slot.event, ForcedMovementEvent)
            and slot.event.phase is EventPhase.COMPLETION
        )
        shove_completion_index = next(
            index
            for index, slot in enumerate(source_slots)
            if isinstance(slot.event, ShoveEvent)
            and slot.event.phase is EventPhase.COMPLETION
        )
        assert forced_completion_index < shove_completion_index

        forced_completion = source_slots[forced_completion_index].event
        assert isinstance(forced_completion, ForcedMovementEvent)
        expected_position_evidence = {
            position_evidence_key((3, 2)): {observer_key},
            position_evidence_key(target.position): {observer_key},
        }
        assert (
            forced_completion.located_position_observer_uuids
            == expected_position_evidence
        )
        assert forced_completion.combat_log is not None
        assert (
            forced_completion.combat_log.located_position_observer_uuids
            == expected_position_evidence
        )

        perspective = _perspective(shover.uuid, controlled=controlled)
        frame = MAPPER.project_frame(
            CausalEventBatch(
                slots=source_slots,
                through_source_event_cursor=EventQueue.event_cursor(),
            ),
            _context(perspective, source_cursor=source_cursor),
        )

        shove_cues = tuple(
            cue
            for cue in frame.presentation
            if isinstance(cue, ShovePresentationCue)
        )
        forced_cues = tuple(
            cue
            for cue in frame.presentation
            if isinstance(cue, ForcedMovementPresentationCue)
        )
        assert len(shove_cues) == 1
        assert len(forced_cues) == 1
        shove_cue = shove_cues[0]
        forced_cue = forced_cues[0]
        assert shove_cue.forced_movement_presentation_id == forced_cue.presentation_id
        assert forced_cue.parent_presentation_id == shove_cue.presentation_id
        assert forced_cue.actor_action_presentation_id == shove_cue.presentation_id
        assert forced_cue.cause is ForcedMovementCause.SHOVE
        assert forced_cue.start_position == (3, 2)
        assert forced_cue.end_position == target.position
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_spectator_union_cannot_combine_forced_movement_endpoint_grants() -> None:
    """Different observers seeing one endpoint each disclose no shove geometry."""
    observer_a = uuid4()
    observer_b = uuid4()
    actor = uuid4()
    target = uuid4()
    perspective = SubjectivePerspective(
        perspective_epoch_id=f"epoch-{observer_a}",
        kind=PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION,
        controlled_entity_uuids=(),
        observer_entity_uuids=(str(observer_a), str(observer_b)),
        active_observer_uuid=str(observer_a),
    )
    shove = ShoveEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        contest_success=True,
        push_distance=5,
        end_position=(6, 5),
        phase=EventPhase.COMPLETION,
        use_register=False,
    ).model_copy(
        update={
            "identified_entity_observer_uuids": {
                str(actor): {str(observer_a), str(observer_b)},
                str(target): {str(observer_a), str(observer_b)},
            },
        },
    )
    forced = ForcedMovementEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        start_position=(5, 5),
        end_position=(6, 5),
        direction=(1, 0),
        intended_distance=5,
        actual_distance=5,
        cause="shove",
        parent_lineage=shove.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    ).model_copy(
        update={
            "identified_entity_observer_uuids": {
                str(actor): {str(observer_a), str(observer_b)},
                str(target): {str(observer_a), str(observer_b)},
            },
            "located_position_observer_uuids": {
                position_evidence_key((5, 5)): {str(observer_a)},
                position_evidence_key((6, 5)): {str(observer_b)},
            },
        },
    )

    frame = MAPPER.project_frame(
        _batch(forced, shove),
        _context(perspective),
    )

    assert not any(
        isinstance(
            cue,
            (ShovePresentationCue, ForcedMovementPresentationCue),
        )
        for cue in frame.presentation
    )
    serialized = frame.model_dump_json().replace(" ", "")
    assert "[5,5]" not in serialized
    assert "[6,5]" not in serialized


def test_real_telekinesis_move_owns_visible_forced_movement() -> None:
    """Telekinesis follow-up completes displacement before its action root."""

    reset_combat_state()
    get_map().create_rectangle(0, 0, 10, 10)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        caster = create_goblin(
            name="Telekinesis Caster",
            position=(2, 2),
            faction="heroes",
        )
        target = create_goblin(
            name="Telekinesis Target",
            position=(3, 2),
            faction="monsters",
        )
        Entity.update_all_entities_senses(max_distance=20)
        observer_key = str(caster.uuid)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {observer_key}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        source_cursor = EventQueue.event_cursor()
        move = TelekinesisMove(
            source_entity_uuid=caster.uuid,
            grabbed_entity_uuid=target.uuid,
            end_position=(5, 2),
        )
        move.behavior_binding = _binding(
            definition_ref=get_content_declaration(TelekinesisMove).ref,
            owner_uuid=caster.uuid,
        )
        result = move.apply()
        assert isinstance(result, ActionEvent)
        assert result.phase is EventPhase.COMPLETION
        assert target.position == (5, 2)

        frame, slots = _project_event_queue_since(
            source_cursor,
            _perspective(caster.uuid, controlled=False),
        )
        forced_slot = next(
            slot
            for slot in slots
            if isinstance(slot.event, ForcedMovementEvent)
            and slot.event.phase is EventPhase.COMPLETION
        )
        action_slot = next(
            slot
            for slot in slots
            if isinstance(slot.event, ActionEvent)
            and slot.event.phase is EventPhase.COMPLETION
            and slot.event.name == "Telekinesis: Move"
        )
        assert forced_slot.source_event_cursor < action_slot.source_event_cursor
        forced_event = forced_slot.event
        assert forced_event.located_position_observer_uuids == {
            position_evidence_key((3, 2)): {observer_key},
            position_evidence_key((5, 2)): {observer_key},
        }

        forced_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, ForcedMovementPresentationCue)
        )
        action_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, ActionPresentationCue)
            and cue.action_name == "Telekinesis: Move"
        )
        assert forced_cue.parent_presentation_id == action_cue.presentation_id
        assert forced_cue.cause is ForcedMovementCause.RULE_EFFECT
        assert action_cue.effect_presentation_ids.count(
            forced_cue.presentation_id
        ) == 1
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_real_thunderwave_owns_visible_forced_movement() -> None:
    """Thunderwave moves before completion and owns its failed-save push."""

    reset_spell_regression_arena(20, 12)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        caster = create_spell_regression_actor(
            "Thunderwave Mapper Caster",
            (5, 5),
            "heroes",
            spell_slots={1: 1},
        )
        target = create_spell_regression_actor(
            "Thunderwave Mapper Target",
            (7, 5),
            "monsters",
        )
        force_save_result(target, "constitution", succeeds=False)
        Entity.update_all_entities_senses(max_distance=100)
        observer_key = str(caster.uuid)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {observer_key}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        source_cursor = EventQueue.event_cursor()
        action = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(12, 5),
            cast_at_level=1,
        )
        action.behavior_binding = _binding(
            definition_ref=get_content_declaration(Thunderwave).ref,
            owner_uuid=caster.uuid,
        )
        with fixed_dice_faces(*([4] * 20)):
            result = action.apply()
        assert isinstance(result, SpellEvent)
        assert not result.canceled
        assert target.position == (9, 5)

        frame, slots = _project_event_queue_since(
            source_cursor,
            _perspective(caster.uuid, controlled=False),
        )
        forced_slot = next(
            slot
            for slot in slots
            if isinstance(slot.event, ForcedMovementEvent)
            and slot.event.phase is EventPhase.COMPLETION
        )
        forced_event = forced_slot.event
        assert forced_event.located_position_observer_uuids == {
            position_evidence_key((7, 5)): {observer_key},
            position_evidence_key((9, 5)): {observer_key},
        }

        forced_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, ForcedMovementPresentationCue)
        )
        spell_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, SpellPresentationCue)
            and cue.spell_id == "thunderwave"
        )
        assert forced_cue.parent_presentation_id == spell_cue.presentation_id
        assert forced_cue.cause is ForcedMovementCause.SPELL
        assert sum(
            target_row.effect_presentation_ids.count(
                forced_cue.presentation_id
            )
            for target_row in spell_cue.targets
        ) == 1
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_real_gust_of_wind_owns_visible_forced_movement() -> None:
    """Gust of Wind moves before completion and owns its failed-save push."""

    reset_spell_regression_arena(30, 14)
    try:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
        caster = create_spell_regression_actor(
            "Gust Mapper Caster",
            (3, 6),
            "heroes",
            spell_slots={2: 1},
        )
        target = create_spell_regression_actor(
            "Gust Mapper Target",
            (7, 6),
            "monsters",
        )
        force_save_result(target, "strength", succeeds=False)
        Entity.update_all_entities_senses(max_distance=140)
        observer_key = str(caster.uuid)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(entity_uuid): {observer_key}
                for entity_uuid in event.get_participant_entity_uuids()
            },
        )
        source_cursor = EventQueue.event_cursor()
        action = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 6),
            cast_at_level=2,
        )
        action.behavior_binding = _binding(
            definition_ref=get_content_declaration(GustOfWind).ref,
            owner_uuid=caster.uuid,
        )
        with fixed_dice_faces(10):
            result = action.apply()
        assert isinstance(result, SpellEvent)
        assert not result.canceled
        assert target.position == (10, 6)

        frame, slots = _project_event_queue_since(
            source_cursor,
            _perspective(caster.uuid, controlled=False),
        )
        forced_slot = next(
            slot
            for slot in slots
            if isinstance(slot.event, ForcedMovementEvent)
            and slot.event.phase is EventPhase.COMPLETION
            and slot.event.target_entity_uuid == target.uuid
        )
        forced_event = forced_slot.event
        assert forced_event.located_position_observer_uuids == {
            position_evidence_key((7, 6)): {observer_key},
            position_evidence_key((10, 6)): {observer_key},
        }

        forced_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, ForcedMovementPresentationCue)
            and cue.entity_uuid == str(target.uuid)
        )
        spell_cue = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, SpellPresentationCue)
            and cue.spell_id == "gust_of_wind"
        )
        assert forced_cue.parent_presentation_id == spell_cue.presentation_id
        assert forced_cue.cause is ForcedMovementCause.SPELL
        assert sum(
            target_row.effect_presentation_ids.count(
                forced_cue.presentation_id
            )
            for target_row in spell_cue.targets
        ) == 1
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_damage_life_transition_reparents_across_technical_siblings() -> None:
    """Damage and death technical nodes become one exact impact transaction."""
    actor = uuid4()
    target = uuid4()
    perspective = _perspective(actor)
    attack = AttackEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.HIT,
        damage_types=[DamageType.SLASHING],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    attack = _visible(attack, actor, identified=(actor, target))
    incoming = Event(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        event_type=EventType.TAKE_DAMAGE,
        parent_lineage=attack.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    damage = _damage(
        source_uuid=actor,
        target_uuid=target,
        parent_lineage=incoming.lineage_uuid,
        amount=10,
        resulting_hp=0,
    )
    damage = _visible(damage, actor, identified=(actor, target))
    technical_death = Event(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        event_type=EventType.DEATH,
        parent_lineage=incoming.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    life = LifeStateChangeEvent(
        source_entity_uuid=target,
        target_entity_uuid=target,
        entity_uuid=target,
        previous_state=LifeState.ALIVE,
        new_state=LifeState.DEAD,
        reason=LifeStateChangeReason.DAMAGE,
        parent_lineage=technical_death.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    life = _visible(life, actor, identified=(target,))

    frame = MAPPER.project_frame(
        _batch(attack, incoming, damage, technical_death, life),
        _context(perspective),
    )

    attack_cue, damage_cue, life_cue = frame.presentation
    assert isinstance(attack_cue, AttackPresentationCue)
    assert isinstance(damage_cue, DamagePresentationCue)
    assert isinstance(life_cue, LifeStatePresentationCue)
    assert attack_cue.child_presentation_ids == (damage_cue.presentation_id,)
    assert damage_cue.child_presentation_ids == (life_cue.presentation_id,)
    assert life_cue.causing_effect_presentation_id == damage_cue.presentation_id
    _assert_closed_graph(frame)


def test_committed_step_events_form_one_ordered_movement_segment() -> None:
    """Only committed contiguous steps determine the renderer trajectory."""
    actor = uuid4()
    perspective = _perspective(actor)
    movement = MovementEvent(
        source_entity_uuid=actor,
        start_position=(1, 1),
        end_position=(3, 1),
        path=((1, 1), (2, 1), (3, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    steps: list[StepMovementEvent] = []
    for path_index, (start, end) in enumerate(
        [((1, 1), (2, 1)), ((2, 1), (3, 1))],
        start=1,
    ):
        step = StepMovementEvent(
            source_entity_uuid=actor,
            from_position=start,
            to_position=end,
            path_index=path_index,
            total_path_length=3,
            trajectory=MovementTrajectory.PATH,
            committed=True,
            parent_lineage=movement.lineage_uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        steps.append(step)

    frame = MAPPER.project_frame(
        _batch(movement, *steps),
        _context(perspective),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, MovementPresentationCue)
    assert cue.trajectory == ((1, 1), (2, 1), (3, 1))
    assert cue.path_start_index == 0
    assert cue.path_total_steps == 2
    assert cue.perception_commit == "observation_frame"


def test_real_move_starts_segments_at_multiple_opportunity_attack_edges() -> None:
    """Each real Move reaction is owned by the segment starting at its step."""
    projection = _project_real_multi_reaction_movement(MovementKind.WALK)

    _assert_exact_reactive_movement_segments(
        projection,
        movement_kind=MovementKind.WALK,
        expected_segments=(
            (0, ((1, 2), (2, 2))),
            (1, ((2, 2), (3, 2), (4, 2), (5, 2))),
            (4, ((5, 2), (6, 2), (7, 2))),
        ),
    )


def test_real_jump_starts_segments_at_multiple_opportunity_attack_edges() -> None:
    """Each real Jump reaction is owned by the segment starting at its step."""
    projection = _project_real_multi_reaction_movement(MovementKind.JUMP)

    _assert_exact_reactive_movement_segments(
        projection,
        movement_kind=MovementKind.JUMP,
        expected_segments=(
            (0, ((1, 2), (2, 2), (3, 2))),
            (2, ((3, 2), (4, 2))),
        ),
    )


def test_lethal_opportunity_attack_keeps_exact_uncommitted_provoking_edge() -> None:
    """A killed mover exposes intent without claiming destination occupancy."""
    mover = uuid4()
    reactor = uuid4()
    perspective = _perspective(mover)
    movement_lineage = uuid4()
    step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(5, 6),
        to_position=(5, 7),
        path_index=1,
        total_path_length=5,
        committed=False,
        parent_lineage=movement_lineage,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = AttackEvent(
        name="Opportunity Attack",
        source_entity_uuid=reactor,
        target_entity_uuid=mover,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        parent_lineage=step.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(
        reaction,
        mover,
        identified=(reactor, mover),
    )

    frame = MAPPER.project_frame(
        _batch(reaction, step),
        _context(perspective),
    )

    attempted = next(
        cue for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    attack = next(
        cue for cue in frame.presentation
        if isinstance(cue, AttackPresentationCue)
    )
    assert attempted.trajectory == ((5, 6), (5, 7))
    assert attempted.path_start_index == 0
    assert attempted.path_total_steps == 4
    assert attempted.model_dump()["endpoint_outcome"] == "not_committed"
    assert attempted.child_presentation_ids == (attack.presentation_id,)
    assert attack.parent_presentation_id == attempted.presentation_id
    assert attack.source_event_cursor < attempted.source_event_cursor
    _assert_closed_graph(frame)


def test_real_lethal_opportunity_attack_projects_attempt_before_death() -> None:
    """The real interrupted Step owns OA, damage, and death without teleporting."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 12, 12)
    try:
        watcher = create_skeleton(
            name="Lethal Reaction Watcher",
            position=(5, 5),
            faction="monsters",
        )
        mover = create_goblin(
            name="Fragile Observable Mover",
            position=(5, 6),
            faction="heroes",
        )
        add_opportunity_attack_handler(watcher)
        force_attack_hit(watcher)
        force_attack_crit(watcher)
        Entity.update_all_entities_senses(max_distance=20)
        observer_key = str(mover.uuid)
        EventQueue.set_identified_entity_observer_computer(
            lambda event: {
                str(participant_uuid): {observer_key}
                for participant_uuid in event.get_participant_entity_uuids()
            },
        )
        source_cursor = EventQueue.event_cursor()

        with fixed_dice_faces(10, 6, 6):
            result = Move(
                source_entity_uuid=mover.uuid,
                end_position=(5, 10),
            ).apply()
        assert isinstance(result, MovementEvent)
        assert result.phase is EventPhase.COMPLETION
        assert mover.health.life_state is LifeState.DEAD
        assert mover.position == (5, 6)

        frame, slots = _project_event_queue_since(
            source_cursor,
            _perspective(mover.uuid, controlled=False),
        )
        completed_step = next(
            slot.event
            for slot in slots
            if isinstance(slot.event, StepMovementEvent)
            and slot.event.phase is EventPhase.COMPLETION
        )
        assert completed_step.committed is False
        assert completed_step.from_position == (5, 6)
        assert completed_step.to_position == (5, 7)
        origin_grants = completed_step.located_position_observer_uuids[
            position_evidence_key((5, 6))
        ]
        destination_grants = completed_step.located_position_observer_uuids[
            position_evidence_key((5, 7))
        ]
        assert observer_key in origin_grants & destination_grants

        attempted = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, MovementPresentationCue)
        )
        attack = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, AttackPresentationCue)
        )
        damage = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, DamagePresentationCue)
        )
        life = next(
            cue
            for cue in frame.presentation
            if isinstance(cue, LifeStatePresentationCue)
        )
        assert attempted.trajectory == ((5, 6), (5, 7))
        assert attempted.endpoint_outcome.value == "not_committed"
        assert attempted.child_presentation_ids == (attack.presentation_id,)
        assert attack.child_presentation_ids == (damage.presentation_id,)
        assert damage.child_presentation_ids == (life.presentation_id,)
        assert life.current is LifeState.DEAD
        _assert_closed_graph(frame)
    finally:
        reset_combat_state()


def test_visible_pre_step_spell_reaction_owns_exact_movement_segment() -> None:
    """A delivered spell reaction resolves before the exact committed edge."""
    mover = uuid4()
    reactor = uuid4()
    perspective = _perspective(mover)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(1, 1),
        end_position=(2, 1),
        path=((1, 1), (2, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(1, 1),
        to_position=(2, 1),
        path_index=1,
        total_path_length=2,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = SpellEvent(
        name="Reactive Ward",
        spell_id="reactive_ward",
        source_entity_uuid=reactor,
        target_entity_uuid=mover,
        spell_school="abjuration",
        spell_level=1,
        cast_at_level=1,
        range_type="ranged",
        parent_lineage=step.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(
        reaction,
        mover,
        identified=(reactor, mover),
    )

    frame = MAPPER.project_frame(
        _batch(reaction, step, movement),
        _context(perspective),
    )

    movement_cue = next(
        cue
        for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    spell_cue = next(
        cue
        for cue in frame.presentation
        if isinstance(cue, SpellPresentationCue)
    )
    assert movement_cue.child_presentation_ids == (
        spell_cue.presentation_id,
    )
    assert spell_cue.parent_presentation_id == movement_cue.presentation_id
    assert spell_cue.source_event_cursor < movement_cue.source_event_cursor
    _assert_closed_graph(frame)


def test_visible_pre_step_shove_reaction_owns_exact_movement_segment() -> None:
    """A delivered resisted shove reaction stays on its exact movement edge."""
    mover = uuid4()
    reactor = uuid4()
    perspective = _perspective(mover)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(1, 1),
        end_position=(2, 1),
        path=((1, 1), (2, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(1, 1),
        to_position=(2, 1),
        path_index=1,
        total_path_length=2,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = ShoveEvent(
        source_entity_uuid=reactor,
        target_entity_uuid=mover,
        contest_success=False,
        parent_lineage=step.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(
        reaction,
        mover,
        identified=(reactor, mover),
    )

    frame = MAPPER.project_frame(
        _batch(reaction, step, movement),
        _context(perspective),
    )

    movement_cue = next(
        cue
        for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    shove_cue = next(
        cue
        for cue in frame.presentation
        if isinstance(cue, ShovePresentationCue)
    )
    assert shove_cue.outcome is ShoveOutcome.RESISTED
    assert movement_cue.child_presentation_ids == (
        shove_cue.presentation_id,
    )
    assert shove_cue.parent_presentation_id == movement_cue.presentation_id
    assert shove_cue.source_event_cursor < movement_cue.source_event_cursor
    _assert_closed_graph(frame)


def test_hidden_step_reaction_does_not_leak_through_movement_segmentation() -> None:
    """Only delivered reactions may create an observable segment boundary."""
    mover = uuid4()
    hidden_reactor = uuid4()
    perspective = _perspective(mover)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(1, 1),
        end_position=(4, 1),
        path=((1, 1), (2, 1), (3, 1), (4, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    steps = [
        StepMovementEvent(
            source_entity_uuid=mover,
            from_position=(path_index, 1),
            to_position=(path_index + 1, 1),
            path_index=path_index,
            total_path_length=4,
            committed=True,
            parent_lineage=movement.lineage_uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        for path_index in range(1, 4)
    ]
    hidden_attack = AttackEvent(
        name="Hidden Opportunity Attack",
        source_entity_uuid=hidden_reactor,
        target_entity_uuid=mover,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        parent_lineage=steps[1].lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    frame = MAPPER.project_frame(
        _batch(movement, steps[0], hidden_attack, steps[1], steps[2]),
        _context(perspective),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, MovementPresentationCue)
    assert cue.trajectory == ((1, 1), (2, 1), (3, 1), (4, 1))
    assert cue.child_presentation_ids == ()
    assert str(hidden_reactor) not in frame.model_dump_json()


def test_visible_reaction_stays_root_when_its_exact_step_is_not_disclosed() -> None:
    """A reaction cannot fall back to another disclosed step from the same Move."""
    observer = uuid4()
    mover = uuid4()
    reactor = uuid4()
    perspective = _perspective(observer, controlled=False)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(1, 1),
        end_position=(3, 1),
        path=((1, 1), (2, 1), (3, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    disclosed_step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(1, 1),
        to_position=(2, 1),
        path_index=1,
        total_path_length=3,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    disclosed_step = _visible(
        disclosed_step,
        observer,
        identified=(mover,),
    ).model_copy(
        update={
            "located_position_observer_uuids": {
                position_evidence_key((1, 1)): {str(observer)},
                position_evidence_key((2, 1)): {str(observer)},
            }
        }
    )
    undisclosed_step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(2, 1),
        to_position=(3, 1),
        path_index=2,
        total_path_length=3,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = AttackEvent(
        name="Visible Opportunity Attack",
        source_entity_uuid=reactor,
        target_entity_uuid=mover,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        parent_lineage=undisclosed_step.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    reaction = _visible(
        reaction,
        observer,
        identified=(reactor, mover),
    )

    frame = MAPPER.project_frame(
        _batch(movement, disclosed_step, reaction, undisclosed_step),
        _context(perspective),
    )

    movement_cue = next(
        cue for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    reaction_cue = next(
        cue for cue in frame.presentation
        if isinstance(cue, AttackPresentationCue)
    )
    assert movement_cue.trajectory == ((1, 1), (2, 1))
    assert movement_cue.child_presentation_ids == ()
    assert reaction_cue.parent_presentation_id is None
    _assert_closed_graph(frame)


def test_post_step_descendant_stays_root_without_splitting_movement() -> None:
    """Only a reaction completed before its exact step may own that edge."""
    mover = uuid4()
    reactor = uuid4()
    perspective = _perspective(mover)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(1, 1),
        end_position=(4, 1),
        path=((1, 1), (2, 1), (3, 1), (4, 1)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    steps = [
        StepMovementEvent(
            source_entity_uuid=mover,
            from_position=(path_index, 1),
            to_position=(path_index + 1, 1),
            path_index=path_index,
            total_path_length=4,
            committed=True,
            parent_lineage=movement.lineage_uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        for path_index in range(1, 4)
    ]
    late_descendant = AttackEvent(
        name="Post-Step Attack",
        source_entity_uuid=reactor,
        target_entity_uuid=mover,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.MISS,
        damage_types=[DamageType.SLASHING],
        parent_lineage=steps[1].lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    late_descendant = _visible(
        late_descendant,
        mover,
        identified=(reactor, mover),
    )

    frame = MAPPER.project_frame(
        _batch(
            movement,
            steps[0],
            steps[1],
            late_descendant,
            steps[2],
        ),
        _context(perspective),
    )

    movement_cue = next(
        cue for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    reaction_cue = next(
        cue for cue in frame.presentation
        if isinstance(cue, AttackPresentationCue)
    )
    assert movement_cue.trajectory == ((1, 1), (2, 1), (3, 1), (4, 1))
    assert movement_cue.child_presentation_ids == ()
    assert reaction_cue.parent_presentation_id is None
    assert reaction_cue.source_event_cursor < movement_cue.source_event_cursor
    _assert_closed_graph(frame)


def test_spectator_keeps_enemy_step_seen_at_both_endpoints() -> None:
    """Pre/post coordinate evidence preserves fully visible enemy movement."""
    observer = uuid4()
    mover = uuid4()
    perspective = _perspective(observer, controlled=False)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(4, 4),
        end_position=(5, 4),
        path=((4, 4), (5, 4)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(4, 4),
        to_position=(5, 4),
        path_index=1,
        total_path_length=2,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = _visible(step, observer, identified=(mover,)).model_copy(
        update={
            "located_position_observer_uuids": {
                position_evidence_key((4, 4)): {str(observer)},
                position_evidence_key((5, 4)): {str(observer)},
            }
        }
    )

    frame = MAPPER.project_frame(
        _batch(movement, step),
        _context(perspective),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, MovementPresentationCue)
    assert cue.trajectory == ((4, 4), (5, 4))


def test_step_completion_freezes_pre_and_post_position_evidence_for_logs() -> None:
    """Effect and completion grants survive on both mapper and log inputs."""
    mover = uuid4()
    observer = uuid4()
    entity_key = str(mover)
    observer_key = str(observer)
    effect = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(7, 7),
        to_position=(8, 7),
        path_index=1,
        total_path_length=2,
        committed=True,
        phase=EventPhase.EFFECT,
        located_entity_observer_uuids={entity_key: {observer_key}},
        located_position_observer_uuids={
            position_evidence_key((7, 7)): {observer_key},
            position_evidence_key((8, 7)): {observer_key},
        },
        use_register=False,
    )

    completion = effect.phase_to(
        EventPhase.COMPLETION,
        located_entity_observer_uuids={entity_key: {observer_key}},
    )

    expected = {
        position_evidence_key((7, 7)): {observer_key},
        position_evidence_key((8, 7)): {observer_key},
    }
    assert completion.located_position_observer_uuids == expected
    assert completion.combat_log is not None
    assert completion.combat_log.located_position_observer_uuids == expected


def test_spell_geometry_is_lossless_and_direct_casts_invent_no_projectile() -> None:
    """Every declared geometry parameter and direct delivery survives projection."""
    caster = uuid4()
    target = uuid4()
    perspective = _perspective(caster)
    cone = SpellEvent(
        name="Cone Spell",
        spell_id="cone_spell",
        source_entity_uuid=caster,
        spell_school="evocation",
        cast_at_level=3,
        range_type="ranged",
        area_geometry=ConePresentationGeometry(
            origin=(1, 1),
            direction=(2, 1),
            length_feet=30,
            angle_degrees=70,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    cube = SpellEvent(
        name="Cube Spell",
        spell_id="cube_spell",
        source_entity_uuid=caster,
        spell_school="evocation",
        cast_at_level=4,
        range_type="ranged",
        area_geometry=CubePresentationGeometry(
            origin=(4, 4),
            direction=None,
            size_feet=20,
            centered=True,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    direct = SpellEvent(
        name="Hold Person",
        spell_id="hold_person",
        source_entity_uuid=caster,
        target_entity_uuid=target,
        spell_school="enchantment",
        cast_at_level=2,
        range_type="ranged",
        projectile_type=None,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    direct = _visible(direct, caster, identified=(caster, target), located=(caster, target))

    frame = MAPPER.project_frame(_batch(cone, cube, direct), _context(perspective))

    cone_cue, cube_cue, direct_cue = frame.presentation
    assert isinstance(cone_cue, SpellPresentationCue)
    assert cone_cue.area == ConeAreaGeometry(
        origin=(1, 1),
        direction=(2, 1),
        length_feet=30,
        angle_degrees=70,
    )
    assert isinstance(cube_cue, SpellPresentationCue)
    assert cube_cue.area == CubeAreaGeometry(
        origin=(4, 4),
        direction=None,
        size_feet=20,
        centered=True,
    )
    assert isinstance(direct_cue, SpellPresentationCue)
    assert direct_cue.delivery is SpellDelivery.DIRECT
    assert direct_cue.projectile_type is None


def test_patch_backed_equipment_door_light_condition_and_terminal_cues() -> None:
    """Complete reducer facts back presentation without any live object lookup."""
    actor = uuid4()
    target = uuid4()
    item_uuid = uuid4()
    door_uuid = uuid4()
    perspective = _perspective(actor)
    prone_ref = _content_ref(
        kind=ContentDefinitionKind.CONDITION,
        content_id="condition.prone",
        digest_char="3",
    )
    snapshot = ItemPresentationState(
        item_uuid=item_uuid,
        semantic_key="test_sword",
        name="Test Sword",
        item_kind=ItemPresentationKind.WEAPON,
        rarity=ItemRarity.COMMON,
        weight=3,
        visual_item_name="Test Sword",
        equipped_visual_policy=EquippedVisualPolicy.VISIBLE,
        stack_count=1,
        max_stack=1,
        is_consumable=False,
    )
    item = ItemLocationStateEvent(
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        item_state=snapshot,
        location=ItemLocation.EQUIPMENT,
        owner_uuid=actor,
        equipment_slot=WeaponSlot.MELEE_MAIN,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    door = SpatialChangeEvent(
        source_entity_uuid=actor,
        event_type=EventType.SPATIAL_OBJECT_CHANGED,
        change_type=SpatialChangeType.OBJECT_CHANGED,
        position=(5, 5),
        object_uuid=door_uuid,
        object_is_open=True,
        object_blocks_movement=False,
        object_blocks_vision=False,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    light = SensoryUpdateEvent(
        source_entity_uuid=actor,
        target_entity_uuid=actor,
        observer_uuid=actor,
        effective_light_levels={"1,1": 2, "2,1": 1},
        cause_event_uuid=door.uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    encounter = EncounterEndEvent(
        source_entity_uuid=actor,
        encounter_uuid=uuid4(),
        combatant_uuids=[actor, target],
        reason="victory",
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    encounter = _visible(encounter, actor, identified=(actor, target))
    condition = ConditionApplicationEvent(
        source_entity_uuid=actor,
        target_entity_uuid=target,
        condition=Prone(
            source_entity_uuid=actor,
            target_entity_uuid=target,
            behavior_binding=_binding(
                definition_ref=prone_ref,
                owner_uuid=target,
            ),
            use_register=False,
        ),
        condition_content_identity=prone_ref.identity_key,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    condition = _visible(condition, actor, identified=(target,))
    loadout = EntityVisualLoadout(
        entity_uuid=str(actor),
        active_weapon_set=ActiveWeaponSet.NONE,
        layers=(),
    )

    frame = MAPPER.project_frame(
        _batch(
            item,
            door,
            light,
            encounter,
            condition,
            patches=(
                VisualLoadoutReplacePatch(loadout=loadout),
                DoorStatePatch(
                    object_uuid=str(door_uuid),
                    position=(5, 5),
                    is_open=True,
                    blocks_movement=False,
                    blocks_vision=False,
                ),
            ),
        ),
        _context(perspective),
    )

    assert any(isinstance(cue, EquipmentPresentationCue) for cue in frame.presentation)
    assert any(isinstance(cue, DoorPresentationCue) for cue in frame.presentation)
    assert any(isinstance(cue, LightPresentationCue) for cue in frame.presentation)
    terminal = next(
        cue for cue in frame.presentation if isinstance(cue, EncounterPresentationCue)
    )
    assert terminal.terminal_barrier is True
    assert terminal.projected_combatant_uuids == (str(actor), str(target))
    condition_cue = next(cue for cue in frame.presentation if cue.kind == "condition")
    assert condition_cue.condition_semantic_key == prone_ref.identity_key
    _assert_closed_graph(frame)


def test_unlocated_spectator_never_receives_spell_area_geometry() -> None:
    """Inherited identity alone cannot disclose an exact caster origin."""
    observer = uuid4()
    caster = uuid4()
    perspective = _perspective(observer, controlled=False)
    spell = SpellEvent(
        name="Cone Spell",
        spell_id="cone_spell",
        source_entity_uuid=caster,
        spell_school="evocation",
        area_geometry=ConePresentationGeometry(
            origin=(99, 99),
            direction=(1, 0),
            length_feet=30,
            angle_degrees=60,
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    spell = _visible(spell, observer, identified=(caster,))

    frame = MAPPER.project_frame(_batch(spell), _context(perspective))

    assert frame.presentation == ()
    assert frame.patches == ()
    assert frame.watermarks.source_event_cursor == 1


def test_boundary_location_grant_does_not_disclose_movement_origin() -> None:
    """One current entity grant cannot authorize both trajectory endpoints."""
    observer = uuid4()
    mover = uuid4()
    perspective = _perspective(observer, controlled=False)
    movement = MovementEvent(
        source_entity_uuid=mover,
        start_position=(50, 50),
        end_position=(51, 50),
        path=((50, 50), (51, 50)),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    movement = _visible(
        movement,
        observer,
        identified=(mover,),
        located=(mover,),
    )
    step = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(50, 50),
        to_position=(51, 50),
        path_index=1,
        total_path_length=2,
        committed=True,
        parent_lineage=movement.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = _visible(step, observer, identified=(mover,), located=(mover,))

    frame = MAPPER.project_frame(_batch(movement, step), _context(perspective))

    assert frame.presentation == ()
    assert "50,50" not in frame.model_dump_json().replace(" ", "")
    assert frame.watermarks.source_event_cursor == 2


def test_source_cursor_gap_fails_closed() -> None:
    """A journal cannot advance across an omitted engine source slot."""
    actor = uuid4()
    event = Event(
        source_entity_uuid=actor,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    batch = CausalEventBatch(
        slots=(ProjectedEventSlot(source_event_cursor=2, event=event),),
        through_source_event_cursor=2,
    )

    with pytest.raises(SubjectiveEventProjectionError, match="begin immediately"):
        MAPPER.project_frame(batch, _context(_perspective(actor)))
