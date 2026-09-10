"""Native condition lifecycles survive capture and replay across actual turns.

The shared producers verify each operation against live HP, life, positions,
condition UUIDs, turn ownership and discovered agency before engine teardown.
These tests then replay only retained values and check the complete sequences.
"""

import random

import pytest

from dnd.actions import AttackEvent, JumpEvent, MovementEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import EventPhase, EventQueue, EventType, SavingThrowEvent, StepMovementEvent
from dnd.core.life_types import LifeState
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage
from tests.game.scenarios import dodge_expiry_history, paralysis_lifecycle


def replay(before: PresentationTarget, roots: tuple[CompletedLineage, ...]) -> tuple[PresentationTarget, ...]:
    assert roots and EventQueue.get_event_by_uuid(roots[0].root.uuid) is None
    states = [before]
    for lineage in roots:
        assert lineage.dispositions == ()
        identities = {event.lineage_uuid for event in lineage.events}
        assert lineage.root.parent_lineage is None
        assert all(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL) for event in lineage.events)
        assert all(event.parent_lineage in identities for event in lineage.events if event is not lineage.root)
        assert all(child in identities for event in lineage.events for child in event.children_lineages)
        states.append(reduce_lineage(states[-1], lineage))
    again = before
    for lineage, expected in zip(roots, states[1:], strict=True):
        again = reduce_lineage(again, lineage)
        assert again == expected
    return tuple(states)


@pytest.mark.parametrize(("behavior", "seeds", "resume", "expected_saves"), [
    pytest.param("action.move", (0,), True, (True,), id="walk-recovers"),
    pytest.param("action.jump", (0,), True, (True,), id="jump-recovers"),
    pytest.param("action.move", (1,), False, (False,), id="failed-save-remains-paralyzed"),
    pytest.param("action.move", (1, 0), True, (False, True), id="later-save-recovers"),
])
def test_native_repeat_saves_remove_exact_owned_conditions_and_restore_movement(
    behavior: str, seeds: tuple[int, ...], resume: bool, expected_saves: tuple[bool, ...],
) -> None:
    random_state = random.getstate()
    before, roots = paralysis_lifecycle(repeat_save_seeds=seeds, movement_behavior=behavior, resume=resume)
    assert random.getstate() == random_state
    states = replay(before, roots)
    move = roots[0]
    assert isinstance(move.root, (MovementEvent, JumpEvent))
    mover = move.root.source_entity_uuid
    assert before.current_actor_uuid == mover and before.actors[mover].conditions == ()
    applied = {fact.name: fact.condition_uuid for fact in move.conditions
               if fact.category is not ConditionCategory.INTERNAL}
    assert set(applied) == {"Paralyzed", "Ghoul Paralysis"}
    assert {fact.condition_uuid for fact in states[1].actors[mover].conditions} == set(applied.values())
    assert states[1].actors[mover].normal_hp == 73
    initial_save, = (event for event in move.events if isinstance(event, SavingThrowEvent))
    assert initial_save.result is False and initial_save.get_dc() == 10
    repeat_roots = tuple(lineage for lineage in roots if lineage.root.event_type is EventType.TURN_END
                         and any(isinstance(event, SavingThrowEvent) for event in lineage.events))
    assert len(repeat_roots) == len(expected_saves)
    for lineage, successful in zip(repeat_roots, expected_saves, strict=True):
        save, = (event for event in lineage.events if isinstance(event, SavingThrowEvent))
        assert lineage.root.source_entity_uuid == mover
        assert save.result is successful and save.get_dc() == 10 and save.target_entity_uuid == mover
        state = states[roots.index(lineage) + 1]
        if successful:
            removed = {fact.name: fact.condition_uuid for fact in lineage.conditions}
            assert removed == applied
            removal_events = {event.uuid: event for event in lineage.events
                              if event.event_type is EventType.CONDITION_REMOVAL}
            assert len(removal_events) == 2
            assert all(event.target_entity_uuid == mover for event in removal_events.values())
            wrapper = next(removal_events[fact.event_uuid] for fact in lineage.conditions
                           if fact.name == "Ghoul Paralysis")
            child = next(removal_events[fact.event_uuid] for fact in lineage.conditions if fact.name == "Paralyzed")
            assert wrapper.parent_lineage == lineage.root.lineage_uuid
            assert child.parent_lineage == wrapper.lineage_uuid
            assert not state.actors[mover].conditions
        else:
            assert not lineage.conditions
            assert {fact.condition_uuid for fact in state.actors[mover].conditions} == set(applied.values())
    final = states[-1]
    assert final.current_actor_uuid == mover and final.round_number == before.round_number + len(seeds)
    assert final.actors[mover].normal_hp == 73 and final.actors[mover].life_state is LifeState.ALIVE
    assert final.senses is not None
    assert final.senses.entities[mover].position == ((2, 3) if resume else (3, 3))
    movements = tuple(lineage for lineage in roots if isinstance(lineage.root, (MovementEvent, JumpEvent)))
    first_step, = (event for event in movements[0].events if isinstance(event, StepMovementEvent))
    assert not first_step.committed
    if resume:
        assert len(movements) == 2
        last_step, = (event for event in movements[-1].events if isinstance(event, StepMovementEvent))
        assert last_step.committed and (last_step.from_position, last_step.to_position) == ((3, 3), (2, 3))
        assert not any(isinstance(event, AttackEvent) for event in movements[-1].events)
        assert {fact.name for fact in final.actors[mover].conditions} == {"Disengaging"}
    else:
        assert len(movements) == 1
        assert {fact.condition_uuid for fact in final.actors[mover].conditions} == set(applied.values())


def test_dodge_survives_the_opposing_action_and_expires_as_its_real_independent_root() -> None:
    random_state = random.getstate()
    before, roots = dodge_expiry_history()
    assert random.getstate() == random_state
    states = replay(before, roots)
    mover = before.current_actor_uuid
    assert mover is not None
    applied, = (fact for fact in roots[0].conditions if fact.name == "Dodging")
    attack_index, = (index for index, lineage in enumerate(roots) if isinstance(lineage.root, AttackEvent))
    assert applied.condition_uuid in {fact.condition_uuid for fact in states[attack_index].actors[mover].conditions}
    assert applied.condition_uuid in {fact.condition_uuid for fact in states[attack_index + 1].actors[mover].conditions}
    expiry_index, = (index for index, lineage in enumerate(roots)
                     if any(fact.condition_uuid == applied.condition_uuid for fact in lineage.conditions)
                     and lineage.root.event_type is EventType.CONDITION_REMOVAL)
    expiry = roots[expiry_index]
    assert attack_index < expiry_index
    assert expiry.root.parent_lineage is None
    assert expiry.conditions[0].condition_uuid == applied.condition_uuid
    assert not states[expiry_index + 1].actors[mover].conditions
    assert states[-1].current_actor_uuid == mover
    assert states[-1].round_number == before.round_number + 1
    assert not states[-1].actors[mover].conditions
