"""Actual damage establishes the baseline; native healing produces replayable facts."""

import random

import pytest

from dnd.core.events import EventPhase, EventQueue, HealEvent, LifeStateChangeEvent
from dnd.core.life_types import LifeState, LifeStateChangeReason
from game.presentation import reduce_lineage
from tests.game.scenarios import healing_history


@pytest.mark.parametrize("dying", (False, True), ids=("living-capped", "dying-restored"))
def test_native_healing_retains_actual_cap_and_authoritative_life_transition_after_reset(dying: bool) -> None:
    random_state = random.getstate()
    before, lineage = healing_history(dying=dying)
    assert random.getstate() == random_state
    root = lineage.root
    assert isinstance(root, HealEvent) and root.target_entity_uuid is not None
    assert EventQueue.get_event_by_uuid(root.uuid) is None
    assert not root.was_blocked and lineage.dispositions == ()
    target = root.target_entity_uuid
    after = reduce_lineage(before, lineage)
    assert after == reduce_lineage(before, lineage)
    assert before.actors[target].maximum_hp == after.actors[target].maximum_hp == 20
    assert before.actors[target].normal_hp == (0 if dying else 13)
    assert before.actors[target].life_state is (LifeState.DYING if dying else LifeState.ALIVE)
    assert root.total_healing == (5 if dying else 20)
    assert root.actual_healing == (5 if dying else 7)
    assert after.actors[target].normal_hp == root.resulting_normal_hp == (5 if dying else 20)
    assert after.actors[target].life_state is LifeState.ALIVE
    assert after.actors[target].temporary_hp == root.resulting_temporary_hp == 0
    assert not before.actors[target].conditions and not after.actors[target].conditions
    assert before.senses is not None and after.senses is not None
    assert before.senses.entities[target].position == after.senses.entities[target].position == (4, 3)
    assert before.senses.position == after.senses.position == (3, 3)
    assert before.actors[before.observer_uuid] == after.actors[before.observer_uuid]
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    assert root.parent_lineage is None
    assert all(event.phase is EventPhase.COMPLETION for event in lineage.events)
    assert all(event.parent_lineage in by_lineage for event in lineage.events if event is not root)
    assert all(child in by_lineage for event in lineage.events for child in event.children_lineages)
    changes = tuple(event for event in lineage.events if isinstance(event, LifeStateChangeEvent))
    if dying:
        change, = changes
        assert change.entity_uuid == target and change.reason is LifeStateChangeReason.HEALING
        assert change.previous_state is LifeState.DYING and change.new_state is LifeState.ALIVE
        assert change.parent_lineage == root.lineage_uuid
        assert change.parent_event in {row.event_uuid for row in lineage.objective_rows
                                       if row.lineage_uuid == root.lineage_uuid}
        assert change.lineage_uuid in root.children_lineages
    else:
        assert root.actual_healing < root.total_healing
        assert not changes
