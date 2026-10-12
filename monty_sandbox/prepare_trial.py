"""Write private configs for a fresh trial using the existing acceptance fixture."""
import argparse
import json
from pathlib import Path

from devtools.player_server_acceptance.fixtures import configuration
from dnd.core.content.encounters import AuthoredCreatureRosterSource, EncounterRecipe, EncounterRosterRecipe
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.audience import SeatAssignment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('.runtime/monty-player-demo'))
    parser.add_argument('--game-port', type=int, default=18891)
    parser.add_argument('--seed', type=int, default=2)
    parser.add_argument('--duel', action='store_true', help='One externally controlled skeleton on each side')
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    config = configuration('two_sides' if args.duel else 'human_vs_ai', directory).model_copy(update={
        'game_id': 'monty-trial', 'test_seed': args.seed})
    if args.duel:
        original = config.recipe
        slots = tuple(slot.model_copy(update={'roster': EncounterRosterRecipe.create(
            roster_id=slot.roster.roster_id, title=slot.roster.title, members=(slot.roster.members[0].model_copy(update={
                'display_name': slot.roster.title + ' duelist',
                'source': AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['skeleton'])}),))})
            for slot in original.roster_slots)
        recipe = EncounterRecipe.create(encounter_id=original.encounter_id, title='Monty agent duel',
            battlefield_id=original.battlefield_id, deployment=original.deployment, roster_slots=slots,
            opening_policy=original.opening_policy)
        config = config.model_copy(update={'recipe': recipe, 'assignments': tuple(
            SeatAssignment(row.seat_id, row.controlled[:1]) for row in config.assignments)})
    seats = {row.seat_id: {'url': f'http://127.0.0.1:{args.game_port}', 'credential': row.token}
        for row in config.credentials}
    for name, value in (('game.json', config.model_dump_json(indent=2)),
                        ('seats.json', json.dumps(seats, indent=2))):
        path = directory / name
        path.touch(mode=0o600, exist_ok=False)
        path.write_text(value)
    print(f'Private trial configuration: {directory}')


if __name__ == '__main__':
    main()
