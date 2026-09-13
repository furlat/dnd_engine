"""Native event-time AI knowledge survives replay without live world owners."""

from contextlib import contextmanager
from collections.abc import Iterator
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from dnd.actions import MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.actor_projection import condition_fact
from dnd.ai.contracts.observation import KnowledgeState
from dnd.ai.runtime.knowledge_reduction import AIKnowledge
from dnd.ai.runtime.movement_revalidation import SubjectiveMovementContinuationGuard
from dnd.ai.runtime.state_projection import SubjectiveAIStateProjector
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.controller import TurnContext
from dnd.core.action_execution import MovementTerminationReason, movement_continuation_scope
from dnd.core.creature_types import DamageType
from dnd.core.events import EntityCreatedEvent, Event, EventPhase, EventQueue, SensoryUpdateEvent, WorldInitializedEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import ProtectionFromEnergyEffect, ShieldBuff
from dnd.spells.necromancy import NoHealing
from dnd.types.actor_facts import ConditionFact
from game.event_record import RecordedEvent
from game.presentation import _retained_event


SOURCE_ROWS = TypeAdapter(list[tuple[int, RecordedEvent, ConditionFact | None]])


@contextmanager
def scene(battlefield: str = "battlefield.open_floor_bright") -> Iterator[Game]:
    reset_engine_runtime()
    build_battlefield(battlefield)
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(game: Game, name: str, position: tuple[int, int], *, compose: bool = True) -> Entity:
    entity = Entity.create(uuid4(), name, config=EntityConfig(
        position=position, faction=name,
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
    ))
    setup_standard_actions(entity)
    if compose:
        entity.compose_entity()
        game.deploy_entity(entity, position)
    return entity


def move(entity: Entity, position: tuple[int, int]) -> MovementEvent:
    available = get_available_actions(entity)
    action, target = next((row, target) for row in available.all_actions
                          if row.behavior_id == "action.move"
                          for target in row.valid_targets if target.position == position)
    result = execute_by_index(entity, action.template_name, target.index, available=available)
    assert isinstance(result, MovementEvent) and not result.canceled
    return result


def context(entity: Entity) -> TurnContext:
    return TurnContext(source_entity_uuid=entity.uuid, entity_uuid=entity.uuid,
                       initiative_order=[entity.uuid])


def source_bytes(observer: UUID) -> bytes:
    """Use the game's existing event/condition recording boundary for this prefix."""
    rows: list[tuple[int, Event, ConditionFact | None]] = []
    for index, event in EventQueue.iter_events_since(0):
        cold = (event.model_copy(update={"use_register": False})
                if isinstance(event, (EntityCreatedEvent, WorldInitializedEvent))
                else _retained_event(event, observer))
        rows.append((index, cold, condition_fact(event, source_index=index)))
    return SOURCE_ROWS.dump_json(rows)


def test_brief_doorway_observation_is_remembered_between_decisions_and_replays() -> None:
    with scene("battlefield.visibility_doorway_open") as game:
        observer = actor(game, "Observer", (5, 7))
        subject = actor(game, "Subject", (8, 4))
        projector = SubjectiveAIStateProjector(assignment_id="doorway", controlled_entity_uuids=(observer.uuid,))
        initial = projector.project_world(observer, context(observer))
        assert str(subject.uuid) not in initial.known_entities
        move(subject, (8, 10))
        assert subject.uuid not in observer.senses.entities
        result = projector.project_world(observer, context(observer))
        remembered = result.known_entities[str(subject.uuid)]
        assert remembered.knowledge_state is KnowledgeState.REMEMBERED
        assert remembered.position == (8, 8)
        assert remembered.normal_hp is None and remembered.conditions == []
        wire = source_bytes(observer.uuid)
        observer_uuid, subject_uuid = observer.uuid, subject.uuid

    assert Entity.get_all_entities() == []
    replay = AIKnowledge((observer_uuid,))
    replay.consume(SOURCE_ROWS.validate_json(wire))
    assert replay.known_entities[str(subject_uuid)] == remembered
    assert replay.observers == result.observers
    assert replay.known_tiles == result.known_tiles
    assert Entity.get_all_entities() == []


def test_hidden_mutations_and_prebirth_conditions_reacquire_current_cold_values() -> None:
    with scene() as game:
        observer = actor(game, "Observer", (0, 3))
        subject = actor(game, "Subject", (4, 3), compose=False)
        for condition in (
            NoHealing(source_entity_uuid=observer.uuid, target_entity_uuid=subject.uuid),
            ProtectionFromEnergyEffect(source_entity_uuid=observer.uuid, target_entity_uuid=subject.uuid,
                                       energy_type=DamageType.FIRE),
            ShieldBuff(source_entity_uuid=observer.uuid, target_entity_uuid=subject.uuid),
        ):
            applied = subject.add_condition(condition)
            assert applied is not None and not applied.canceled
        subject.compose_entity()
        projector = SubjectiveAIStateProjector(assignment_id="discovery", controlled_entity_uuids=(observer.uuid,))
        before = projector.project_world(observer, context(observer))
        assert str(subject.uuid) not in before.known_entities
        subject.receive_damage(7, DamageType.FORCE, source_entity_uuid=subject.uuid)
        game.deploy_entity(subject, subject.position)
        acquired = projector.project_world(observer, context(observer)).known_entities[str(subject.uuid)]
        assert acquired.normal_hp == subject.get_normal_hp() == 33
        assert acquired.healing_blocked is True
        assert "Fire" in acquired.damage_resistances
        assert acquired.ac == subject.ac_bonus().normalized_score
        assert acquired.effect_protections and acquired.effect_protections[0].blocked_effect_ids
        assert acquired.condition_facts and all(row.applied_source_event_cursor is not None for row in acquired.condition_facts)
        assert subject.remove_condition("No Healing")
        assert subject.remove_condition("Protection from Energy")
        subject.health.add_temporary_hit_points(8, subject.uuid)
        after = projector.project_world(observer, context(observer))
        current = after.known_entities[str(subject.uuid)]
        assert current.healing_blocked is False and current.damage_resistances == []
        assert current.temporary_hp == 8 and current.hp == 41
        wire = source_bytes(observer.uuid)
        observer_uuid, subject_uuid = observer.uuid, subject.uuid

    replay = AIKnowledge((observer_uuid,))
    replay.consume(SOURCE_ROWS.validate_json(wire))
    assert replay.known_entities[str(subject_uuid)] == current
    assert replay.known_tiles == after.known_tiles
    assert Entity.get_all_entities() == []


def test_shared_observers_keep_visible_actor_when_only_one_observer_loses_it() -> None:
    with scene("battlefield.visibility_doorway_open") as game:
        first = actor(game, "First", (5, 7))
        second = actor(game, "Second", (10, 7))
        subject = actor(game, "Subject", (8, 7))
        projector = SubjectiveAIStateProjector(assignment_id="shared", controlled_entity_uuids=(first.uuid, second.uuid))
        initial = projector.project_world(first, context(first))
        assert initial.known_entities[str(subject.uuid)].observer_uuids == sorted([str(first.uuid), str(second.uuid)])
        move(first, (5, 4))
        final = projector.project_world(first, context(first))
        retained = final.known_entities[str(subject.uuid)]
        assert retained.knowledge_state is KnowledgeState.VISIBLE
        assert retained.observer_uuids == [str(second.uuid)] and retained.normal_hp == 40
        assert len(final.observers) == 2


def test_native_movement_guard_learns_at_step_before_movement_root_completes() -> None:
    with scene("battlefield.visibility_doorway_open") as game:
        observer = actor(game, "Observer", (8, 4))
        subject = actor(game, "Hostile", (5, 7))
        projector = SubjectiveAIStateProjector(assignment_id="guard", controlled_entity_uuids=(observer.uuid,))
        initial = projector.project_world(observer, context(observer))
        boundaries: list[int] = []

        def advance():
            assert not any(isinstance(event, MovementEvent) and event.phase is EventPhase.COMPLETION
                           for _, event in EventQueue.iter_events_since(0))
            boundaries.append(EventQueue.event_cursor())
            return projector.project_world(observer, context(observer))

        guard = SubjectiveMovementContinuationGuard(actor_uuid=str(observer.uuid), world=initial, project_world=advance)
        with movement_continuation_scope(guard):
            result = move(observer, (8, 10))
        assert result.phase is EventPhase.COMPLETION
        assert result.termination_reason is MovementTerminationReason.SUBJECTIVE_REVALIDATION
        assert observer.position == (8, 6) and len(boundaries) == 2
        assert guard.world.known_entities[str(subject.uuid)].normal_hp == 40
        assert any(isinstance(event, SensoryUpdateEvent) and subject.uuid in event.entity_contacts_changed
                   for _, event in EventQueue.iter_events_since(0))
