# Agent-written, reusable source. Save with execute(save_as='scouts').
# These helpers take explicit game refs/data and keep no implicit match history.


def combat_summary(records):
    attacks = []
    deaths = []
    for packet in records:
        entries = [node['combat_log'] for lineage in packet.get('lineages', [])
            for node in lineage['events'] if node['combat_log']]
        entries += [row['entry'] for row in packet.get('combat_log_appends', [])]
        for entry in entries:
            if entry['entry_type'] == 'attack':
                attacks.append(entry['compact'])
            if entry['entry_type'] == 'death':
                deaths.append(entry['compact'])
    return {'attacks': attacks, 'deaths': deaths}


async def game_summary(game_ref):
    after = -1
    attacks = []
    deaths = []
    while True:
        page = await game_events(game_ref, after=after, limit=64)
        summary = combat_summary(page['records'])
        attacks += summary['attacks']
        deaths += summary['deaths']
        after = page['next_after']
        if not page['has_more']:
            break
    observation = await game_read(game_ref)
    return {'game_ref': game_ref, 'identity': observation['identity'], 'mode': observation['mode'],
        'record_count': observation['record_count'], 'attack_count': len(attacks), 'deaths': deaths,
        'boundary': observation['status']['boundary'], 'cursor': observation['cursor']}


async def play_steps(game_ref, max_actions=12):
    focus_uuid = None
    steps = []
    for _ in range(max_actions):
        observation = await game_wait(game_ref, timeout_seconds=10)
        boundary = observation['status']['boundary']
        if observation['wait_timed_out'] or boundary['lifecycle'] != 'waiting_for_human':
            break
        discovery = await game_choices(game_ref)
        choices = discovery['choices']
        controlled = observation['audience']['controlled']
        attacks = [(row, target) for row in choices['entity_actions']
            if row['performs_attack'] and row['can_afford']
            for target in row['valid_targets'] if target['target_uuid'] not in controlled]
        intent = {'kind': 'end_turn'}
        label = 'End turn'
        if attacks:
            row, target = sorted(attacks, key=lambda pair: (
                pair[1]['target_uuid'] != focus_uuid,
                pair[0]['weapon_slot'] != 'MELEE_MAIN', pair[1]['distance'] or 0))[0]
            selection = {'action_index': row['discovery_index'],
                'target_indices': [target['index']], 'extra_target_positions': []}
            checked = await game_preview(game_ref, choices['entity_uuid'], discovery['state_revision'],
                choices['discovery_generation'], selection)
            if not checked['preview']['can_confirm']:
                break
            focus_uuid = target['target_uuid']
            intent = {'kind': 'execute_selection',
                'discovery_generation': choices['discovery_generation'], 'selection': selection}
            label = row['display_name'] + ' -> ' + target['target_name']
        print(label)
        outcome = await game_act(game_ref, choices['entity_uuid'], discovery['state_revision'], intent)
        steps.append({'actor': choices['entity_uuid'], 'action': label,
            'receipt': outcome['receipt']['kind'], 'command': outcome['receipt']['command_number']})
        if outcome['receipt']['kind'] != 'committed':
            break
    return {'game': await game_summary(game_ref), 'steps': steps}
