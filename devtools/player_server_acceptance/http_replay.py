"""Cold-check real HTTP prefixes with the existing shared player reducer."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from dnd.player.reduction import reduce_initialization, reduce_operation
from server.protocol import InitializationResponse, PlayerOperation
from devtools.player_server_acceptance.replay import check_group, check_hud, records, require, sdk


def replay(directory: Path) -> list[dict]:
    receipt = json.loads((directory / 'result.json').read_bytes())
    reports = []
    for seat, expected_commands in receipt['commands'].items():
        events, lineages, commands = {}, set(), []
        counts, logs = Counter(), sha256()
        paths = records(directory / seat)
        require(len(paths) == receipt['records'][seat], 'Consumer record count differs')
        total_bytes = 0
        state = None
        for sequence, path in enumerate(paths):
            raw = path.read_bytes()
            total_bytes += len(raw)
            packet = sdk.decode('InitializationResponse' if sequence == 0 else 'PlayerOperation', raw)
            sdk.check_protocol(packet['protocol'])
            require(int(path.stem) == sequence == packet['cursor']['sequence'], 'Recording sequence differs')
            if sequence == 0:
                scope = {key: packet['cursor'][key] for key in ('game_id', 'game_epoch', 'audience_id')}
                controlled = set(packet['initialization']['audience']['controlled'])
                check_group(packet['initialization'], controlled, events, lineages, counts, logs)
                initial = InitializationResponse.model_validate_json(raw)
                state = reduce_initialization(initial.initialization, content_additions=initial.content_additions)
                initial_actors = [{'name': actor.name, 'hp': actor.normal_hp, 'maximum_hp': actor.maximum_hp}
                    for actor in sorted(state.actors.values(), key=lambda value: value.name)]
            else:
                require(all(packet['cursor'][key] == value for key, value in scope.items()), 'Scope changed')
                require(set(packet['audience']['controlled']) == controlled, 'Control changed')
                require(packet['boundary']['input_actor_uuid'] is None or packet['boundary']['input_actor_uuid'] in controlled,
                    'Foreign input authority')
                for group in packet['lineages']:
                    check_group(group, controlled, events, lineages, counts, logs)
                check_hud(packet['hud'], controlled)
                state = reduce_operation(state, PlayerOperation.model_validate_json(raw))
                if packet['command_number'] is not None:
                    commands.append(packet['command_number'])
            require(all(row['visibility'] in ('public', 'observed') for row in packet['content_additions']), 'Private content admitted')
        require(total_bytes == receipt['bytes'][seat], 'Consumer byte count differs')
        require(packet['cursor'] == receipt['consumed'][seat], 'Consumer cursor differs')
        require(commands == list(range(1, expected_commands + 1)), 'Own commands are not exactly once/in order')
        terminal = packet.get('boundary', {}).get('lifecycle') == 'terminal'
        require(not receipt['terminal'] or terminal, 'Completed follower has no terminal public boundary')
        require(state is not None, 'Empty prefix')
        require(all(actor.controlled_items is None or str(actor.uuid) in controlled for actor in state.actors.values()),
            'Reduced foreign inventory')
        reports.append({'lane': directory.name, 'seat': seat, 'records': len(paths), 'commands': len(commands),
            'bytes': total_bytes, 'final_cursor': packet['cursor'], 'reducer_cursor': state.reducer_cursor,
            'closed_occurrences': len(events), 'closed_lineages': len(lineages), 'catalog_entries': len(state.content),
            'terminal': terminal, 'terminal_expected': receipt['terminal'], 'initial_actors': initial_actors,
            'facts': dict(counts),
            'actors': [{'name': actor.name, 'hp': actor.normal_hp, 'controlled': str(actor.uuid) in controlled,
                'life_state': actor.life_state.value} for actor in sorted(state.actors.values(), key=lambda value: value.name)]})
    return reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'prefixes': [row for directory in args.inputs for row in replay(directory)]}
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({'prefixes': len(result['prefixes']), 'records': sum(row['records'] for row in result['prefixes'])}))


if __name__ == '__main__':
    main()
