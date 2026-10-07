"""Finite combat choices through SDK discovery and ordered native previews."""
from time import perf_counter
from uuid import uuid4

from dnd_player import choices, preview


def affordable(discovered):
    return [row for key in ('entity_actions', 'position_actions', 'self_actions', 'object_actions')
        for row in discovered[key] if row['can_afford'] and row['valid_targets']]


def pick_action(case, seat, actor, rows, progress):
    """Choose a requested action; all returned targets were offered by the engine."""
    attacks = [(row, target) for row in rows if row['performs_attack']
        for target in row['valid_targets'] if target['target_uuid'] is not None]
    movement = next((row for row in rows if row['behavior_id'] == 'action.move'), None)
    weapon = [(row, target) for row, target in attacks if row['behavior_id'] == 'action.attack'
        and row['weapon_slot'] == ('MELEE_MAIN' if case == 'melee' else 'RANGED_MAIN')]
    if movement is not None and attacks and (not progress.get((actor, 'moved')) or case == 'melee' and not weapon):
        target_position = min(attacks, key=lambda pair: pair[1]['distance'] or 0)[1]['position']
        if target_position is not None:
            options = [target for target in movement['valid_targets'] if target['position'] != target_position]
            if options:
                target = min(options, key=lambda row: (abs(row['position'][0] - target_position[0])
                    + abs(row['position'][1] - target_position[1]), row['path_cost'] or 0))
                if case != 'melee':
                    # One ordinary step is sufficient to measure movement without
                    # deliberately bringing ranged actors into melee reach.
                    options = [row for row in options if row['path_cost'] and row['path_cost'] <= 5]
                    if options:
                        target = max(options, key=lambda row: abs(row['position'][0] - target_position[0])
                            + abs(row['position'][1] - target_position[1]))
                return movement, target
    casts = progress.get((actor, 'casts'), 0)
    if seat == 'amber' and case not in ('melee', 'ranged'):
        wanted = 'spell.fireball' if case == 'fireball_six_goblins' else 'spell.' + case
        budget = 3 if case in ('magic_missile', 'scorching_ray') else 1
        candidates = [row for row in rows if row['behavior_id'] == wanted and casts < budget]
        if case == 'wall_of_fire':
            candidates = [row for row in candidates if {facet['key']: facet['value'] for facet in row['variant_facets']}.get('form') == 'segment']
        if candidates:
            row = min(candidates, key=lambda item: (item['cast_at_level'] or 0, item['discovery_index']))
            if case in ('magic_missile', 'scorching_ray', 'hold_person'):
                target = min(row['valid_targets'], key=lambda item: item['target_name'] or '')
            elif case == 'fireball_six_goblins':
                target = min(row['valid_targets'], key=lambda item: (
                    -sum(name.startswith('Blue') for name in item['affected_entity_names'] or ()),
                    sum(name.startswith('Amber') for name in item['affected_entity_names'] or ()),
                    abs(item['position'][0] - 10) + abs(item['position'][1] - 7)))
            else:
                center = (9, 7) if case == 'wall_of_fire' else (7, 7)
                target = min(row['valid_targets'], key=lambda item: abs(item['position'][0] - center[0])
                    + abs(item['position'][1] - center[1]))
            return row, target
        if casts and case in ('wall_of_fire', 'conjure_animals') and not progress.get((actor, 'concentration_dropped')):
            row = next((row for row in rows if row['behavior_id'] == 'action.drop_concentration'), None)
            if row is not None:
                return row, row['valid_targets'][0]
        cantrip = next((row for row in rows if row['behavior_id'] == 'spell.fire_bolt'), None)
        if cantrip is not None:
            return cantrip, cantrip['valid_targets'][0]
    return min(weapon, key=lambda pair: pair[1]['distance'] or 0) if weapon else None


async def intent(connection, case, seat, actor, revision, progress):
    if progress.pop((actor, 'end_turn'), False):
        return {'kind': 'end_turn'}, {'action': 'end_turn', 'discovery_ms': None, 'preview_ms': [], 'targets': []}
    started = perf_counter()
    answer = await choices(connection, {'actor_uuid': actor, 'state_revision': revision,
        'force_attack': False, 'correlation_id': str(uuid4())})
    discovery_ms = (perf_counter() - started) * 1000
    discovered = answer['choices']
    chosen = pick_action(case, seat, actor, affordable(discovered), progress)
    evidence = {'action': 'end_turn', 'discovery_ms': discovery_ms, 'preview_ms': [], 'targets': []}
    if chosen is None:
        return {'kind': 'end_turn'}, evidence
    row, target = chosen
    selection = {'action_index': row['discovery_index'], 'target_indices': [target['index']], 'extra_target_positions': []}
    evidence.update(action=row['behavior_id'], display_name=row['display_name'], cast_at_level=row['cast_at_level'],
        variant_facets=row['variant_facets'], targets=[target['target_name'] or target['position']],
        affected_count=target['affected_count'])
    repeated = case in ('magic_missile', 'scorching_ray') and row['behavior_id'] == 'spell.' + case
    first_uuid = target['target_uuid']
    second_uuid = next((item['target_uuid'] for item in row['valid_targets']
        if item['target_uuid'] != first_uuid), first_uuid)
    for _ in range(16):
        started = perf_counter()
        result = await preview(connection, {'actor_uuid': actor, 'state_revision': revision,
            'discovery_generation': discovered['discovery_generation'], 'correlation_id': str(uuid4()), 'selection': selection})
        evidence['preview_ms'].append((perf_counter() - started) * 1000)
        offered = result['preview']
        if offered['can_confirm'] and (not repeated or len(selection['target_indices']) >= 3):
            break
        if offered['next_targets']:
            wanted = second_uuid if len(selection['target_indices']) == 1 else first_uuid
            next_target = next((item for item in offered['next_targets'] if item['target_uuid'] == wanted), offered['next_targets'][0])
            selection['target_indices'].append(next_target['index'])
            evidence['targets'].append(next_target['target_name'] or next_target['position'])
        elif offered['next_positions']:
            endpoint = min(offered['next_positions'], key=lambda position: abs(position[0] - 10) + abs(position[1] - 8))
            selection['extra_target_positions'].append(endpoint)
            evidence['targets'].append(endpoint)
        else:
            raise AssertionError({'action': row['behavior_id'], 'selection': selection, 'preview': offered})
    else:
        raise AssertionError('Native selection did not complete within 16 inputs')
    if row['behavior_id'] == 'action.move':
        progress[actor, 'moved'] = True
    elif row['behavior_id'] == 'action.drop_concentration':
        progress[actor, 'concentration_dropped'] = True
    elif seat == 'amber' and row['behavior_id'] not in ('spell.fire_bolt', 'action.attack'):
        progress[actor, 'casts'] = progress.get((actor, 'casts'), 0) + 1
    if row['behavior_id'] not in ('action.move', 'action.drop_concentration'):
        progress[actor, 'end_turn'] = True
    return {'kind': 'execute_selection', 'discovery_generation': discovered['discovery_generation'], 'selection': selection}, evidence
