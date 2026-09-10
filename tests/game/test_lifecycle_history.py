"""Native death saves and revival replay after teardown with their real ancestry."""

import random

import pytest

from dnd.actions import AttackEvent, MovementEvent
from dnd.core.events import (
    DeathEvent, DeathSaveEvent, EventPhase, EventQueue, EventType, HealEvent,
    LifeStateChangeEvent, ReviveEvent, StepMovementEvent,
)
from dnd.core.life_types import LifeState, LifeStateChangeReason
from game.presentation import reduce_lineage
from tests.game.scenarios import attack_history, lifecycle_history


@pytest.mark.parametrize(("seeds", "heal_after", "revive_after", "save_results", "final_state", "final_hp"), [
    pytest.param((0,), False, False, ((13, 1, 0),), LifeState.DYING, 0, id="ordinary-success"),
    pytest.param((1,), False, False, ((5, 0, 1),), LifeState.DYING, 0, id="ordinary-failure"),
    pytest.param((31,), False, False, ((1, 0, 2),), LifeState.DYING, 0, id="critical-failure"),
    pytest.param((5,), False, False, ((20, 0, 0),), LifeState.ALIVE, 1, id="critical-recovery"),
    pytest.param((0, 0, 0), True, False, ((13, 1, 0), (13, 2, 0), (13, 0, 0)),
                 LifeState.ALIVE, 5, id="stabilization-and-healing"),
    pytest.param((1, 0, 31), False, True, ((5, 0, 1), (13, 1, 1), (1, 0, 3)),
                 LifeState.ALIVE, 3, id="death-and-explicit-revival"),
])
def test_native_turn_saves_and_recovery_preserve_life_hp_and_complete_ancestry(
    seeds: tuple[int, ...], heal_after: bool, revive_after: bool,
    save_results: tuple[tuple[int, int, int], ...], final_state: LifeState, final_hp: int,
) -> None:
    random_state = random.getstate()
    before, roots = lifecycle_history(save_seeds=seeds, heal_after=heal_after, revive_after=revive_after)
    assert random.getstate() == random_state
    target, = (actor.uuid for actor in before.actors.values() if actor.life_state is LifeState.DYING)
    assert target != before.observer_uuid and before.current_actor_uuid == before.observer_uuid
    assert before.actors[target].normal_hp == 0 and before.actors[target].conditions == ()
    assert before.senses is not None and before.senses.entities[target].position == (4, 3)
    saves: list[DeathSaveEvent] = []
    states = [before]
    for lineage in roots:
        assert EventQueue.get_event_by_uuid(lineage.root.uuid) is None
        assert lineage.dispositions == () and lineage.root.parent_lineage is None
        by_lineage = {event.lineage_uuid: event for event in lineage.events}
        assert all(event.phase is EventPhase.COMPLETION for event in lineage.events)
        assert all(event.parent_lineage in by_lineage for event in lineage.events if event is not lineage.root)
        assert all(child in by_lineage for event in lineage.events for child in event.children_lineages)
        for event in lineage.events:
            if event is not lineage.root:
                assert event.parent_event in {row.event_uuid for row in lineage.objective_rows
                                              if row.lineage_uuid == event.parent_lineage}
        after = reduce_lineage(states[-1], lineage)
        assert after == reduce_lineage(states[-1], lineage)
        assert after.actors[before.observer_uuid] == before.actors[before.observer_uuid]
        assert after.actors[target].conditions == () and after.actors[target].temporary_hp == 0
        states.append(after)
        root_saves = tuple(event for event in lineage.events if isinstance(event, DeathSaveEvent))
        if not root_saves:
            continue
        save, = root_saves
        saves.append(save)
        assert lineage.root.event_type is EventType.TURN_START
        assert lineage.root.source_entity_uuid == target
        assert save.parent_lineage == lineage.root.lineage_uuid and save.entity_uuid == target
        assert save.natural_roll is not None and save.succeeded == (save.natural_roll >= 10)
        changes = tuple(event for event in lineage.events if isinstance(event, LifeStateChangeEvent))
        if save.regained_hit_point:
            heal, = (event for event in lineage.events if isinstance(event, HealEvent))
            change, = changes
            assert save.natural_roll == 20 and heal.actual_healing == heal.resulting_normal_hp == 1
            assert heal.parent_lineage == save.lineage_uuid and change.parent_lineage == heal.lineage_uuid
            assert change.reason is LifeStateChangeReason.HEALING
            assert change.previous_state is LifeState.DYING and change.new_state is LifeState.ALIVE
            assert after.actors[target].normal_hp == 1 and after.actors[target].life_state is LifeState.ALIVE
        elif save.became_stable:
            change, = changes
            assert change.parent_lineage == save.lineage_uuid
            assert change.reason is LifeStateChangeReason.STABILIZATION
            assert change.previous_state is LifeState.DYING and change.new_state is LifeState.STABLE
            assert after.actors[target].normal_hp == 0 and after.actors[target].life_state is LifeState.STABLE
        elif save.died:
            death, = (event for event in lineage.events if isinstance(event, DeathEvent))
            change, = changes
            assert death.parent_lineage == save.lineage_uuid and change.parent_lineage == death.lineage_uuid
            assert change.reason is LifeStateChangeReason.DEATH_SAVE_FAILURES
            assert change.previous_state is LifeState.DYING and change.new_state is LifeState.DEAD
            assert after.actors[target].normal_hp == 0 and after.actors[target].life_state is LifeState.DEAD
            assert after.senses is not None and target not in after.senses.entities
        else:
            assert not changes and after.actors[target].life_state is LifeState.DYING
    assert tuple((save.natural_roll, save.successes, save.failures) for save in saves) == save_results
    final = states[-1]
    assert final.actors[target].life_state is final_state and final.actors[target].normal_hp == final_hp
    assert final.current_actor_uuid == (before.observer_uuid if heal_after or revive_after else target)
    assert final.round_number == before.round_number + len(seeds)
    assert final.senses is not None and final.senses.entities[target].position == (4, 3)
    # Both halves of every native turn remain separate roots, including round
    # boundaries. The save tree is a child of its own TurnStart, never a new head.
    expected_turns = 2 * len(seeds) - (0 if heal_after or revive_after else 1)
    assert sum(lineage.root.event_type is EventType.TURN_START for lineage in roots) == expected_turns
    assert sum(lineage.root.event_type is EventType.TURN_END for lineage in roots) == expected_turns
    assert sum(lineage.root.event_type is EventType.ROUND_START for lineage in roots) == len(seeds)
    assert sum(lineage.root.event_type is EventType.ROUND_END for lineage in roots) == len(seeds)
    if heal_after or revive_after:
        recovery = roots[-1]
        assert roots[-2].root.event_type is EventType.TURN_START
        assert roots[-2].root.source_entity_uuid == before.observer_uuid
        assert states[-3].actors[target] == states[-2].actors[target]
        change, = (event for event in recovery.events if isinstance(event, LifeStateChangeEvent))
        assert change.parent_lineage == recovery.root.lineage_uuid and change.new_state is LifeState.ALIVE
        assert change.normal_hit_points == final_hp
        if revive_after:
            assert isinstance(recovery.root, ReviveEvent) and recovery.root.hit_points == 3
            assert states[-2].actors[target].life_state is LifeState.DEAD
            assert change.reason is LifeStateChangeReason.REVIVAL and change.previous_state is LifeState.DEAD
        else:
            assert isinstance(recovery.root, HealEvent) and recovery.root.actual_healing == 5
            assert states[-2].actors[target].life_state is LifeState.STABLE
            assert change.reason is LifeStateChangeReason.HEALING and change.previous_state is LifeState.STABLE


def test_native_opportunity_damage_downs_player_without_committing_the_interrupted_step() -> None:
    random_state = random.getstate()
    before, lineage = attack_history(
        "weapon.longsword", 17, opportunity=True, whole_movement=True,
        maximum_hp=4, uses_death_saves=True,
    )
    assert random.getstate() == random_state and EventQueue.get_event_by_uuid(lineage.root.uuid) is None
    assert isinstance(lineage.root, MovementEvent) and lineage.dispositions == ()
    mover = lineage.root.source_entity_uuid
    after = reduce_lineage(before, lineage)
    assert before.actors[mover].normal_hp == before.actors[mover].maximum_hp == 4
    assert before.actors[mover].life_state is LifeState.ALIVE
    assert after.actors[mover].normal_hp == 0 and after.actors[mover].life_state is LifeState.DYING
    assert after.actors[mover].conditions == ()
    assert after.senses is not None and after.senses.entities[mover].position == (3, 3)
    step, = (event for event in lineage.events if isinstance(event, StepMovementEvent))
    attack, = (event for event in lineage.events if isinstance(event, AttackEvent))
    change, = (event for event in lineage.events if isinstance(event, LifeStateChangeEvent))
    assert not step.committed and step.from_position == (3, 3) and step.to_position == (2, 3)
    assert attack.parent_lineage == step.lineage_uuid
    assert change.entity_uuid == mover and change.new_state is LifeState.DYING
    assert change.reason is LifeStateChangeReason.DAMAGE
    assert not any(isinstance(event, DeathEvent) for event in lineage.events)
