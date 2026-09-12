"""The same public player encounter completes across layouts and camera views."""

import os
import random
from pathlib import Path
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from dnd.core.base_actions import AvailableActionsResult
from game.controls import ActionSelection, EndTurn
from game.encounter_play import GameSummary, run
from game.player_facts import DamageFact, PlayerState, SpellFact


def check_layout(
    quadrant: int,
    players: tuple[tuple[int, int], tuple[int, int]],
    enemies: tuple[tuple[int, int], tuple[int, int]],
    *,
    capture_dir: Path | None = None,
) -> GameSummary:
    acted: set[UUID] = set()
    first_hp: dict[UUID, int] = {}
    allocated: list[UUID] = []

    def choose(target: PlayerState, available: AvailableActionsResult) -> ActionSelection | EndTurn:
        actor = target.current_actor_uuid
        assert actor is not None
        if not first_hp:
            first_hp.update((identity, value.normal_hp) for identity, value in target.actors.items())
        if actor in acted:
            return EndTurn()
        acted.add(actor)
        missile = next(((index, row) for index, row in enumerate(available.all_actions)
                        if row.behavior_id == "spell.magic_missile" and row.num_projectiles == 3
                        and row.valid_targets), None)
        if missile is not None:
            index, row = missile
            hostile = tuple(option for option in row.valid_targets if option.target_uuid is not None
                            and target.actors[option.target_uuid].creature_content_ref is not None)
            assert len(hostile) == 2 and row.num_projectiles == 3 and row.allow_same_target
            selected = tuple(hostile[index % len(hostile)] for index in range(row.num_projectiles))
            allocated.extend(option.target_uuid for option in selected if option.target_uuid is not None)
            return ActionSelection(index, tuple(option.index for option in selected))
        index, row = next((index, row) for index, row in enumerate(available.all_actions)
                          if row.behavior_id == "action.dodge" and row.valid_targets)
        return ActionSelection(index, (row.valid_targets[0].index,))

    previous = random.getstate()
    random.seed(0)
    try:
        result = run(collect_frames=True, player_input=choose, stop_after_commands=4, frame_deltas=(0.1,), max_frames=180,
                     quadrant=quadrant, player_positions=players, enemy_positions=enemies, capture_dir=capture_dir)
    finally:
        random.setstate(previous)

    assert result.player_commands == 4 and len(acted) == 2
    assert result.historical == result.latest
    assert result.historical.current_actor_uuid in acted and result.historical.round_number == 2
    assert result.frames[-1].pending == 0
    casts = [lineage for lineage in result.lineages if isinstance(lineage.root.fact, SpellFact)]
    assert len(casts) == 1
    root = casts[0].root.fact
    assert isinstance(root, SpellFact) and root.behavior_id == "spell.magic_missile"
    assert tuple(root.declared_target_entity_uuids) == tuple(allocated)
    assert allocated[0] == allocated[2] and allocated[0] != allocated[1]
    assert casts[0].root.uuid not in {identity for identity, _ in result.presentation_gaps}
    applied = [event.fact for event in casts[0].events
               if isinstance(event.fact, DamageFact) and event.fact.stage == "applied"]
    assert len(applied) == 3
    for lineage in result.lineages:
        for event in lineage.events:
            fact = event.fact
            if isinstance(fact, DamageFact) and fact.stage == "applied":
                assert fact.resulting_normal_hp is not None
                first_hp[fact.target_entity_uuid] = fact.resulting_normal_hp
    assert {identity: actor.normal_hp for identity, actor in result.historical.actors.items()} == first_hp
    assert dict(result.frames[-1].hit_points) == {str(identity): hp for identity, hp in first_hp.items()}
    return result


@pytest.mark.parametrize("quadrant,players,enemies", (
    (0, ((5, 5), (5, 7)), ((9, 5), (9, 7))),
    (1, ((9, 5), (9, 7)), ((5, 5), (5, 7))),
    (2, ((5, 5), (7, 5)), ((5, 9), (7, 9))),
    (3, ((4, 4), (5, 3)), ((9, 9), (10, 8))),
), ids=("east", "west-swapped", "south", "diagonal"))
def test_discovered_player_actions_and_native_round_settle_in_each_layout(quadrant, players, enemies) -> None:
    check_layout(quadrant, players, enemies)
