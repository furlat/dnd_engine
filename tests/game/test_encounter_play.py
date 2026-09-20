"""Public commands produce a whole encounter through the actual SDL frame pump."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.player_facts import ActionFact, AttackFact, MovementFact
from game.controls import ActionSelection, EndTurn
from game.encounter_play import run


def test_full_round_moves_conditions_and_enemy_actions_while_history_paused() -> None:
    stages = {}
    commands = 0

    def choose(target, available):
        nonlocal commands
        actor = target.current_actor_uuid
        stage = stages.get(actor, 0)
        stages[actor] = stage + 1
        commands += 1
        if stage == 2:
            if commands == 6:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            return EndTurn()
        behavior = "action.move" if stage == 0 else "action.dodge"
        index, action = next((index, row) for index, row in enumerate(available.all_actions)
                             if row.behavior_id == behavior and row.valid_targets)
        destination = min(action.valid_targets, key=lambda option: option.path_cost or 0)
        return ActionSelection(index, (destination.index,))

    state = random.getstate()
    random.seed(0)
    try:
        # Native ranged delivery and each Jump leg keep their authored duration.
        # The public settled-round boundary still determines when the run ends.
        result = run(player_input=choose, stop_after_commands=6, frame_deltas=(0.1,), max_frames=240,
                     collect_frames=True,
                     frame_events={80: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),)})
    finally:
        random.setstate(state)
    assert result.player_commands == 6
    assert result.latest == result.historical
    assert result.historical.round_number == 2
    assert any(isinstance(lineage.root.fact, MovementFact) for lineage in result.lineages)
    assert len({lineage.root.fact.source_entity_uuid for lineage in result.lineages
                if isinstance(lineage.root.fact, AttackFact)}) == 2
    paused = [frame for frame in result.frames if frame.paused]
    assert len(paused) > 3
    assert len({frame.historical_cursor for frame in paused}) == 1
    assert len({frame.elapsed_ms for frame in paused}) == 1
    assert paused[-1].latest_cursor > paused[0].latest_cursor
    assert not any(frame.input_ready for frame in paused)
    assert len({frame.positions for frame in result.frames}) > 6
    assert all(frame.historical_cursor <= frame.latest_cursor for frame in result.frames)


def test_authored_workshop_plays_a_discovered_lever_action_in_the_same_frame_pump() -> None:
    commands = 0

    def choose(target, available):
        nonlocal commands
        commands += 1
        if commands == 2:
            return EndTurn()
        lever = next(obj for obj in target.objects.values() if obj.item.item_id == "environment.trap_lever")
        index, action = next((index, row) for index, row in enumerate(available.all_actions)
                             if row.source_item_uuid == lever.item.item_uuid and row.valid_targets)
        return ActionSelection(index, (action.valid_targets[0].index,))

    state = random.getstate()
    random.seed(0)
    try:
        result = run(encounter_id="encounter.residue_workshop", player_input=choose,
                     stop_after_commands=2, frame_deltas=(0.1,), max_frames=400, collect_frames=True)
    finally:
        random.setstate(state)
    assert result.player_commands == 2 and result.latest == result.historical
    assert result.historical.round_number == 2
    assert not result.presentation_gaps
    assert any(isinstance(lineage.root.fact, ActionFact) for lineage in result.lineages)
    assert len(result.latest.actors) == 5
    assert any(obj.item.is_engaged for obj in result.latest.objects.values())
    assert any(frame.root_uuid is not None for frame in result.frames)
