"""Finite combat choices through SDK discovery and ordered native previews."""
from time import perf_counter
from uuid import uuid4

from dnd_player import (action_options, all_actions, binding_position, binding_subject, binding_value,
    choices, next_options, preview, preview_positions, selection_for)


def affordable(discovered):
    return [row for row in all_actions(discovered) if row['can_afford'] and action_options(discovered, row)]


def pick_action(case, seat, actor, discovered, rows, progress):
    """Choose a requested action; all returned targets were offered by the engine."""
    attacks = [(row, target) for row in rows if row['performs_attack']
        for target in action_options(discovered, row) if binding_subject(discovered, target) is not None]
    movement = next((row for row in rows if row['behavior_id'] == 'action.move'), None)
    weapon = [(row, target) for row, target in attacks if row['behavior_id'] == 'action.attack'
        and row['weapon_slot'] == ('MELEE_MAIN' if case == 'melee' else 'RANGED_MAIN')]
    if movement is not None and attacks and (not progress.get((actor, 'moved')) or case == 'melee' and not weapon):
        target_position = binding_position(discovered, min(attacks, key=lambda pair: binding_value(pair[1], 'distance') or 0)[1])
        if target_position is not None:
            options = [target for target in action_options(discovered, movement) if binding_position(discovered, target) != target_position]
            if options:
                target = min(options, key=lambda row: (abs(binding_position(discovered, row)[0] - target_position[0])
                    + abs(binding_position(discovered, row)[1] - target_position[1]), binding_value(row, 'path_cost') or 0))
                if case != 'melee':
                    # One ordinary step is sufficient to measure movement without
                    # deliberately bringing ranged actors into melee reach.
                    options = [row for row in options if binding_value(row, 'path_cost') and binding_value(row, 'path_cost') <= 5]
                    if options:
                        target = max(options, key=lambda row: abs(binding_position(discovered, row)[0] - target_position[0])
                            + abs(binding_position(discovered, row)[1] - target_position[1]))
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
                target = min(action_options(discovered, row), key=lambda item: (binding_subject(discovered, item) or {}).get('name') or '')
            elif case == 'fireball_six_goblins':
                # The fixture places its six disclosed goblins around this aim.
                # Inspect only the chosen preview; choices deliberately omit effects.
                target = min(action_options(discovered, row), key=lambda item:
                    abs(binding_position(discovered, item)[0] - 10)
                    + abs(binding_position(discovered, item)[1] - 7))
            else:
                center = (9, 7) if case == 'wall_of_fire' else (7, 7)
                target = min(action_options(discovered, row), key=lambda item: abs(binding_position(discovered, item)[0] - center[0])
                    + abs(binding_position(discovered, item)[1] - center[1]))
            return row, target
        if casts and case in ('wall_of_fire', 'conjure_animals') and not progress.get((actor, 'concentration_dropped')):
            row = next((row for row in rows if row['behavior_id'] == 'action.drop_concentration'), None)
            if row is not None:
                return row, action_options(discovered, row)[0]
        cantrip = next((row for row in rows if row['behavior_id'] == 'spell.fire_bolt'), None)
        if cantrip is not None:
            return cantrip, action_options(discovered, cantrip)[0]
    return min(weapon, key=lambda pair: binding_value(pair[1], 'distance') or 0) if weapon else None


async def intent(connection, case, seat, actor, revision, progress):
    if progress.pop((actor, 'end_turn'), False):
        return {'kind': 'end_turn'}, {'action': 'end_turn', 'discovery_ms': None, 'preview_ms': [], 'targets': []}
    started = perf_counter()
    answer = await choices(connection, {'actor_uuid': actor, 'state_revision': revision,
        'force_attack': False, 'correlation_id': str(uuid4())})
    discovery_ms = (perf_counter() - started) * 1000
    discovered = answer['choices']
    chosen = pick_action(case, seat, actor, discovered, affordable(discovered), progress)
    evidence = {'action': 'end_turn', 'discovery_ms': discovery_ms, 'preview_ms': [], 'targets': []}
    if chosen is None:
        return {'kind': 'end_turn'}, evidence
    row, target = chosen
    selection = selection_for(row, [target])
    evidence.update(action=row['behavior_id'], display_name=row['display_name'], cast_at_level=row['cast_at_level'],
        variant_facets=row.get('variant_facets', []),
        targets=[(binding_subject(discovered, target) or {}).get('name') or binding_position(discovered, target)],
        affected_count=None)
    repeated = case in ('magic_missile', 'scorching_ray') and row['behavior_id'] == 'spell.' + case
    first_uuid = (binding_subject(discovered, target) or {}).get('uuid')
    second_uuid = next((subject['uuid'] for item in action_options(discovered, row)
        if (subject := binding_subject(discovered, item)) is not None and subject['uuid'] != first_uuid), first_uuid)
    for _ in range(16):
        started = perf_counter()
        result = await preview(connection, {'actor_uuid': actor, 'state_revision': revision,
            'discovery_generation': discovered['discovery_generation'], 'correlation_id': str(uuid4()), 'selection': selection})
        evidence['preview_ms'].append((perf_counter() - started) * 1000)
        offered = result['preview']
        if offered.get('area_preview') == 'computed':
            evidence['affected_count'] = len(offered.get('affected_entity_uuids', ()))
        extend_wall = (case == 'wall_of_fire' and row['behavior_id'] == 'spell.wall_of_fire'
            and not selection['extra_target_positions'] and bool(preview_positions(offered)))
        if offered['can_confirm'] and not extend_wall and (not repeated or len(selection['target_indices']) >= 3):
            break
        if options := next_options(offered):
            wanted = second_uuid if len(selection['target_indices']) == 1 else first_uuid
            next_target = next((item for item in options
                if (binding_subject(offered, item) or {}).get('uuid') == wanted), options[0])
            selection['target_indices'].append(next_target['index'])
            evidence['targets'].append((binding_subject(offered, next_target) or {}).get('name') or binding_position(offered, next_target))
        elif positions := preview_positions(offered):
            endpoint = min(positions, key=lambda position: abs(position[0] - 10) + abs(position[1] - 8))
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
