"""Opportunity attacks use exact endpoint reach and retain native step ancestry."""

import pytest

from dnd.actions import AttackEvent, Disengage, Move
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, StepMovementEvent
from dnd.entity import Entity
from dnd.game import Game
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.physical_access import ContactPassage
from tests.engine.test_window_attack_access import barrier, combatants


@pytest.fixture
def arena():
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


@pytest.mark.parametrize("guard", [None, "barrier", "disengage"])
def test_long_reach_reacts_only_on_departure_with_native_step_parent(arena, guard):
    source, mover, _ = combatants(arena, "creature.stegosaurus_tail")
    add_opportunity_attack_handler(source)
    if guard == "barrier":
        barrier(ContactPassage.BLOCKED)
    Entity.update_all_entities_senses()

    candidates = ((2, 2), (3, 2), (4, 2), (5, 2), (20, 20))
    expected = [] if guard == "barrier" else [(3, 2), (4, 2)]
    assert source.senses.get_threathened_positions(candidate_positions=iter(candidates)) == expected
    full_threat = source.senses.get_threathened_positions()
    assert [position for position in candidates if position in full_threat] == expected
    assert source.senses.get_threathened_positions(
        candidate_positions=candidates, close_pressure=True) == expected[:1]

    if guard == "disengage":
        disengage = Disengage(source_entity_uuid=mover.uuid).apply()
        assert disengage is not None and not disengage.canceled
    cursor = EventQueue.event_cursor()
    first = Move(source_entity_uuid=mover.uuid, end_position=(4, 2)).apply()
    assert first is not None and not first.canceled and mover.position == (4, 2)
    assert source.action_economy.reactions.normalized_score == 1
    assert not any(isinstance(event, AttackEvent)
        for _, event in EventQueue.iter_events_since(cursor))

    # A miss keeps the movement outcome simple while preserving a real attack,
    # reaction payment and all native causal events on the departing step.
    hp = mover.get_hp()
    with fixed_dice_faces(1):
        second = Move(source_entity_uuid=mover.uuid, end_position=(5, 2)).apply()
    assert second is not None and not second.canceled and mover.position == (5, 2)
    assert mover.get_hp() == hp
    completed = [event for _, event in EventQueue.iter_events_since(cursor)
        if event.phase is EventPhase.COMPLETION]
    attacks = [event for event in completed
        if isinstance(event, AttackEvent) and event.name == "Opportunity Attack"]
    assert len(attacks) == int(guard is None)
    assert source.action_economy.reactions.normalized_score == int(guard is not None)
    if attacks:
        departing = next(event for event in completed if isinstance(event, StepMovementEvent)
            and event.parent_lineage == second.lineage_uuid)
        assert (departing.from_position, departing.to_position) == ((4, 2), (5, 2))
        assert departing.committed
        assert attacks[0].parent_lineage == departing.lineage_uuid
        assert attacks[0].source_entity_uuid == source.uuid
        assert attacks[0].target_entity_uuid == mover.uuid
