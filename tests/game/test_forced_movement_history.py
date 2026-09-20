"""Native forced movement keeps costs, outcomes and complete spatial children."""

import random

import pytest

from devtools.animation_review.cases import ForcedMovementCase, load_cases
from devtools.animation_review.produce import produce
from dnd.actions import AttackEvent, ShoveEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.events import EventPhase, EventQueue, ForcedMovementEvent, SpatialChangeEvent, SpatialChangeType, StepMovementEvent, TakeDamageEvent
from dnd.core.life_types import LifeState
from game.presentation import reduce_lineage


@pytest.mark.parametrize(("case_id", "expected_end", "distance", "blocked", "damage"), [
    ("shove-success", (6, 3), 10, False, ()),
    ("shove-resisted", (4, 3), 0, False, ()),
    ("shove-blocked", (4, 3), 0, True, ()),
    ("shove-partly-blocked", (5, 3), 5, True, ()),
    ("shove-no-opportunity", (6, 3), 10, False, ()),
    ("shove-stairs-up", (16, 22), 10, False, ()),
    ("shove-stairs-down", (16, 24), 10, False, ()),
    ("shove-goblin", (6, 3), 10, False, ()),
    ("shove-spikes", (2, 12), 10, False, (5, 7)),
    ("shove-spikes-lethal", (2, 11), 5, False, (5,)),
    ("telekinesis-displacement", (6, 4), 15, False, ()),
])
def test_discovered_forced_actions_preserve_native_outcomes_after_runtime_reset(
    case_id: str, expected_end: tuple[int, int], distance: int, blocked: bool, damage: tuple[int, ...],
) -> None:
    case = next(case for case in load_cases() if case.id == case_id)
    scenario = case.scenario
    assert isinstance(scenario, ForcedMovementCase)
    previous = random.getstate()
    sequence = produce(case)
    assert random.getstate() == previous
    assert len(sequence.lineages) == 1
    lineage = sequence.lineages[0]
    assert lineage.root.parent_lineage is None and lineage.root.phase is EventPhase.COMPLETION
    assert not lineage.dispositions
    assert not any(isinstance(event, (StepMovementEvent, AttackEvent)) for event in lineage.events)
    identities = {event.lineage_uuid for event in lineage.events}
    for event in lineage.events:
        assert EventQueue.get_event_by_uuid(event.uuid) is None
        assert event.phase is EventPhase.COMPLETION
        assert event.parent_lineage in identities or event is lineage.root
        assert all(child in identities for child in event.children_lineages)

    forced = tuple(event for event in lineage.events if isinstance(event, ForcedMovementEvent))
    assert len(forced) == (1 if distance else 0)
    if scenario.mechanism == "shove":
        assert isinstance(lineage.root, ShoveEvent)
        assert lineage.root.contest_success is (case_id != "shove-resisted")
        assert lineage.root.push_distance == distance
        assert bool(lineage.root.blocked_by) is blocked
        target_uuid = lineage.root.target_entity_uuid
    else:
        assert isinstance(lineage.root, ActionEvent)
        assert lineage.root.behavior_id == "action.spell.telekinesis.move"
        target_uuid = forced[0].target_entity_uuid
        assert "Concentrating" in {condition.name for condition in sequence.before.actors[sequence.before.observer_uuid].conditions}
    assert target_uuid is not None
    if forced:
        event = forced[0]
        assert event.parent_lineage == lineage.root.lineage_uuid
        assert (event.start_position, event.end_position) == (scenario.target_position, expected_end)
        assert event.actual_distance == distance
        assert event.intended_distance == (15 if scenario.mechanism == "telekinesis" else 10)
        assert event.blocked_by_obstacle is blocked
        assert event.cause == scenario.mechanism

    entries = tuple(event for event in lineage.events if isinstance(event, SpatialChangeEvent)
                    and event.change_type is SpatialChangeType.ENTITY_ENTERED and event.entity_uuid == target_uuid)
    assert len(entries) == (1 if scenario.mechanism == "telekinesis" else distance // 5)
    assert all(event.parent_lineage == forced[0].lineage_uuid for event in entries)
    if entries:
        assert entries[-1].position == expected_end
    damage_events = tuple(event for event in lineage.events if isinstance(event, TakeDamageEvent))
    assert tuple(event.final_damage for event in damage_events) == damage
    if damage:
        assert tuple(event.position for event in entries) == ((2, 11), (2, 12))[:len(damage)]
        # Raising a ready trap is a causal child between entry and damage;
        # already-raised spikes can apply their payload directly on entry.
        by_lineage = {event.lineage_uuid: event for event in lineage.events}
        for applied, entry in zip(damage_events, entries, strict=True):
            ancestor = applied
            while ancestor.parent_lineage != entry.lineage_uuid:
                assert ancestor.parent_lineage is not None
                ancestor = by_lineage[ancestor.parent_lineage]
        assert lineage.events.index(damage_events[-1]) < lineage.events.index(forced[0])

    before = sequence.before.actors[target_uuid]
    after = reduce_lineage(sequence.before, lineage).actors[target_uuid]
    assert before.normal_hp > 0
    assert after.normal_hp == before.normal_hp - sum(damage)
    assert after.life_state is (LifeState.DEAD if case_id == "shove-spikes-lethal" else LifeState.ALIVE)
    if after.life_state is LifeState.ALIVE:
        assert after.last_visual_position == expected_end
    if scenario.target_identity is None:
        assert before.items and before.equipment
    else:
        assert before.creature_content_ref == scenario.target_identity
    if "stairs" in case_id:
        assert [sequence.before.tiles[entry.position].elevation_steps for entry in entries] == (
            [1, 2] if case_id.endswith("up") else [1, 0])
