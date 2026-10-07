"""SDK crypt journey using the production headless reducer, never live entities."""
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from dnd_player import (Follower, acknowledge, attach, choices, connect, follow,
    preview, receipt, status, submit_command, wait_for_cursor)
from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization, reduce_operation
from player_server.protocol import InitializationResponse, PlayerOperation


# These are the existing authored dungeon's walkthrough goals, not a pathfinder.
STEPS = (
    ('Expedition supplies', 'open'), ('Expedition supplies', 'loot'),
    ('Vault door', 'open'), ('move', (5, 10)), ('potion', None),
    ('Sealed cache', 'open'), ('Sealed cache', 'loot'), ('move', (5, 8)),
    ('Vault trap lever', 'pull'), ('Crypt passage', 'open'),
    ('move', (10, 6)), ('Burial hall door', 'open'), ('move', (13, 6)),
)


def available_rows(discovered):
    return [row for key in ('entity_actions', 'position_actions', 'self_actions', 'object_actions')
            for row in discovered[key] if row['can_afford'] and row['valid_targets']]


def move_toward(discovered, current, destinations):
    distance = lambda p: min(abs(p[0]-d[0])+abs(p[1]-d[1]) for d in destinations)
    candidates = [(row, target) for row in available_rows(discovered) if row['behavior_id'] == 'action.move'
        for target in row['valid_targets'] if target['position'] is not None
        and distance(target['position']) < distance(current)]
    return min(candidates, key=lambda pair: (distance(pair[1]['position']), pair[1]['path_cost'] or 0), default=None)


def planned_selection(state, actor, discovered, stage, leader):
    current = state.actors[UUID(actor)].last_visual_position
    rows = available_rows(discovered)
    if stage < len(STEPS):
        if actor != leader:
            return None, stage
        name, verb = STEPS[stage]
        if name == 'move':
            if tuple(current) == verb:
                return planned_selection(state, actor, discovered, stage+1, leader)
            return move_toward(discovered, current, (verb,)), stage
        if name == 'potion':
            row = next((r for r in rows if r['behavior_id']=='action.item.potion_healing.drink'), None)
            return ((row, row['valid_targets'][0]) if row else None), stage+1 if row else stage
        identity = next((str(key) for key, value in state.objects.items() if value.item.name == name), None)
        option = next((o for o in discovered['world_interactions'] if o['subject_uuid']==identity
            and (o['behavior_id'].endswith('.'+verb) or verb=='loot' and 'loot' in o['behavior_id'])), None)
        if option is None:
            raise AssertionError(f'Missing observed interaction at stage {stage}: {name} {verb}')
        for row in rows:
            if row['behavior_id'] != option['behavior_id'] or row['template_name'] != option['template_name']:
                continue
            target = next((t for t in row['valid_targets'] if row['source_item_uuid']==identity
                           or t['target_uuid']==identity), None)
            if target is not None:
                return (row, target), stage+1
        return move_toward(discovered, current, option['contact_positions']), stage
    enemies = {str(key) for key, value in state.actors.items() if key not in state.viewing_audience.controlled
               and value.present and value.normal_hp > 0}
    attacks = [(row, target) for row in rows
        if row['performs_attack'] or row['behavior_id']=='spell.magic_missile'
        for target in row['valid_targets'] if target['target_uuid'] in enemies]
    if attacks:
        return min(attacks, key=lambda pair: (pair[0]['behavior_id']!='spell.magic_missile',
            pair[0]['behavior_id']!='spell.fire_bolt', pair[1]['distance'] or 0)), stage
    # Move through the already opened passage using native offered routes.
    destination = (7, 6) if current[0] < 7 else (12, 6) if current[0] < 12 else (16, 6)
    return move_toward(discovered, current, (destination,)), stage


async def play():
    output = Path(os.environ['PLAYER_OUTPUT']); output.mkdir(parents=True, exist_ok=True)
    connection = await connect(os.environ['PLAYER_URL'], os.environ['PLAYER_TOKEN'])
    while connection.bootstrap['status']['published_cursor'] is None:
        await connection.http.aclose()
        await asyncio.sleep(.05)
        connection = await connect(os.environ['PLAYER_URL'], os.environ['PLAYER_TOKEN'])
    await attach(connection, {'acquisition_id':str(uuid4()),
        'expected_attachment_epoch':connection.bootstrap['status']['attachment_epoch']})
    state: PlayerState | None = None
    records = 0
    byte_count = 0
    async def consume(packet, raw):
        nonlocal state, records, byte_count
        byte_count += len(raw)
        if byte_count > 128*1024*1024:
            raise RuntimeError('Crypt recording quota exceeded')
        (output/f"{packet['cursor']['sequence']:06}.json").write_bytes(raw)
        if packet['kind']=='initialization':
            parsed = InitializationResponse.model_validate_json(raw)
            state = reduce_initialization(parsed.initialization, content_additions=parsed.content_additions)
        else:
            assert state is not None
            state = reduce_operation(state, PlayerOperation.model_validate_json(raw))
        records += 1
    follower = Follower(connection, consume)
    following = asyncio.create_task(follow(follower))
    stage = commands = 0
    leader = None
    trace = []
    try:
        async with asyncio.timeout(240):
            while not following.done():
                now = await status(connection)
                if now['published_cursor'] is not None:
                    await wait_for_cursor(follower, now['published_cursor'])
                actor = now['boundary']['input_actor_uuid']
                if actor is None:
                    await asyncio.sleep(.02)
                    continue
                assert state is not None
                leader = leader or actor
                await acknowledge(connection, follower.consumed)
                revision = now['boundary']['state_revision']
                answer = await choices(connection, {'actor_uuid':actor,'state_revision':revision,
                    'force_attack':False,'correlation_id':str(uuid4())})
                discovered = answer['choices']
                selected, next_stage = planned_selection(state,actor,discovered,stage,leader)
                intent = {'kind':'end_turn'}
                label = 'End turn'
                if selected is not None:
                    row,target = selected
                    selection = {'action_index':row['discovery_index'],'target_indices':[target['index']],
                                 'extra_target_positions':[]}
                    # Use the native ordered-prefix contract, including repeated rays.
                    for _ in range(12):
                        result = await preview(connection, {'actor_uuid':actor,'state_revision':revision,
                            'discovery_generation':discovered['discovery_generation'],
                            'correlation_id':str(uuid4()),'selection':selection})
                        if result['preview']['can_confirm']:
                            break
                        options = result['preview']['next_targets']
                        if not options:
                            raise AssertionError(result)
                        selection['target_indices'].append(options[0]['index'])
                    else:
                        raise AssertionError('Selection never became complete')
                    intent = {'kind':'execute_selection','discovery_generation':discovered['discovery_generation'],
                              'selection':selection}
                    label = row['display_name']
                command = {'command_number':now['next_command_number'],'actor_uuid':actor,
                           'state_revision':revision,'intent':intent}
                outcome = await submit_command(connection,command)
                while outcome['receipt']['kind']=='pending':
                    await asyncio.sleep(.01)
                    outcome = await receipt(connection,command['command_number'])
                assert outcome['receipt']['kind']=='committed', outcome
                await wait_for_cursor(follower,outcome['receipt']['cursor'])
                stage = next_stage
                commands += 1
                trace.append({'command':commands,'stage':stage,'action':label,'actor':state.actors[UUID(actor)].name,
                              'position':state.actors[UUID(actor)].last_visual_position,
                              'hp':state.actors[UUID(actor)].normal_hp})
                (output/'trace.json').write_text(json.dumps(trace,indent=2))
                print(json.dumps(trace[-1]),flush=True)
                assert commands < 120, 'Crypt did not terminate'
            await following
        assert stage == len(STEPS) and follower.completed
        (output/'result.json').write_text(json.dumps({'language':'python-shared-reducer','commands':commands,
            'records':records,'bytes':byte_count,'final_cursor':follower.consumed,'terminal':follower.completed,
            'walkthrough_steps':stage}))
    finally:
        following.cancel()
        await asyncio.gather(following,return_exceptions=True)
        await connection.http.aclose()


if __name__=='__main__':
    asyncio.run(play())
