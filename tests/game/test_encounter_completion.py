"""Discovered human choices and native turns reach the real encounter ending."""

import os
import random
from pathlib import Path
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from dnd.core.base_actions import ActionAvailabilityStatus, AvailableActionsResult
from dnd.core.events import EventType
from dnd.core.life_types import LifeState
from game.controls import ActionSelection, EndTurn
from game.encounter_play import GameSummary, run
from game.player_facts import ConditionChangeFact, DamageFact, MovementFact, PlayerState, SpellFact, TurnFact


def check_encounter_completion(*, capture_dir: Path | None = None) -> GameSummary:
    steps: dict[tuple[int, UUID], int] = {}
    expected_hp: dict[UUID, int] = {}
    spell_rounds: list[int] = []
    spent_spell_rounds: list[int] = []
    fighter_uuids: set[UUID] = set()

    def choose(target: PlayerState, available: AvailableActionsResult) -> ActionSelection | EndTurn:
        actor = target.current_actor_uuid
        assert actor is not None
        living_hostiles = {identity for identity, state in target.actors.items()
                           if state.creature_content_ref is not None and state.life_state is LifeState.ALIVE}
        assert living_hostiles, "human input must close after the encounter ends"
        if not expected_hp:
            expected_hp.update((identity, state.normal_hp) for identity, state in target.actors.items())
        turn = target.round_number, actor
        step = steps.get(turn, 0)
        steps[turn] = step + 1
        missile = next(((index, row) for index, row in enumerate(available.all_actions)
                        if row.behavior_id == "spell.magic_missile" and row.num_projectiles == 3), None)
        if missile is not None:
            index, row = missile
            if step:
                assert row.availability_status is ActionAvailabilityStatus.SOURCE_UNAFFORDABLE
                assert not row.can_afford and not row.valid_targets
                spent_spell_rounds.append(target.round_number)
                return EndTurn()
            assert row.can_afford and row.allow_same_target
            hostile = tuple(option for option in row.valid_targets if option.target_uuid in living_hostiles)
            assert hostile
            spell_rounds.append(target.round_number)
            return ActionSelection(index, tuple(hostile[dart % len(hostile)].index for dart in range(3)))

        fighter_uuids.add(actor)
        if target.round_number == 1 and step == 0:
            index, move = next((index, row) for index, row in enumerate(available.all_actions)
                               if row.behavior_id == "action.move" and row.valid_targets)
            destination = next(option for option in move.valid_targets if option.position == (6, 5))
            assert destination.path_cost == 5 and available.remaining_movement == 30
            return ActionSelection(index, (destination.index,))
        if target.round_number == 1 and step == 1:
            assert available.remaining_movement == 25
            index, dodge = next((index, row) for index, row in enumerate(available.all_actions)
                                if row.behavior_id == "action.dodge" and row.valid_targets)
            return ActionSelection(index, (dodge.valid_targets[0].index,))
        return EndTurn()

    previous = random.getstate()
    random.seed(0)
    try:
        result = run(player_input=choose, frame_deltas=(0.1,), max_frames=200,
                     player_positions=((5, 5), (5, 7)), enemy_positions=((9, 5), (9, 7)),
                     capture_dir=capture_dir)
    finally:
        random.setstate(previous)

    assert result.encounter_ended and result.historical == result.latest
    assert spell_rounds == [1, 2] and spent_spell_rounds == [1]
    assert result.historical.round_number == 2 and result.historical.current_actor_uuid is None
    enemies = [state for state in result.historical.actors.values() if state.creature_content_ref is not None]
    assert len(enemies) == 2 and all(state.life_state is LifeState.DEAD for state in enemies)
    endings = [lineage for lineage in result.lineages if isinstance(lineage.root.fact, TurnFact)
               and lineage.root.fact.event_type is EventType.ENCOUNTER_END]
    assert len(endings) == 1
    ending_frame = next(frame.index for frame in result.frames if frame.root_uuid == endings[0].root.uuid)
    after_end = [frame for frame in result.frames if frame.index > ending_frame]
    assert len(after_end) >= 5 and not any(frame.input_ready for frame in after_end)
    assert all(frame.pending == 0 and frame.historical_cursor == frame.latest_cursor for frame in after_end)
    assert len(fighter_uuids) == 1
    fighter_uuid = next(iter(fighter_uuids))
    assert any(isinstance(lineage.root.fact, MovementFact) and lineage.root.fact.source_entity_uuid == fighter_uuid
               for lineage in result.lineages)
    casts = [lineage.root.fact for lineage in result.lineages if isinstance(lineage.root.fact, SpellFact)]
    assert len(casts) == 2
    for lineage in result.lineages:
        for event in lineage.events:
            fact = event.fact
            if isinstance(fact, DamageFact) and fact.stage == "applied":
                assert fact.resulting_normal_hp is not None
                expected_hp[fact.target_entity_uuid] = fact.resulting_normal_hp
    conditions = [event.fact for lineage in result.lineages for event in lineage.events
                  if isinstance(event.fact, ConditionChangeFact)]
    dodge = next(fact.condition for fact in conditions if fact.condition.name == "Dodging")
    removed = any(fact.event_type is EventType.CONDITION_REMOVAL
                  and fact.condition.condition_uuid == dodge.condition_uuid for fact in conditions)
    assert (dodge.condition_uuid in {condition.condition_uuid for condition in result.historical.actors[fighter_uuid].conditions}) is not removed
    assert {identity: state.normal_hp for identity, state in result.historical.actors.items()} == expected_hp
    return result


def test_encounter_finishes_with_resources_conditions_and_input_settled() -> None:
    check_encounter_completion()
