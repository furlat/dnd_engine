"""Compact discovery and preview admit only well-scoped, ordered selections."""
from copy import deepcopy
import json

import pytest

from dnd_player import (action_options, all_actions, binding_path, binding_position,
    binding_subject, binding_value, next_options, position_eligibility,
    preview_positions, secondary_options, selection_for)
from dnd_player import transport as sdk

UUID = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'


def action(index, target_set, target_type='multi_entity', **changes):
    return {'template_name': 'Rule', 'behavior_id': 'spell.rule', 'provided_by_id': 'spell.rule',
        'target_type': target_type, 'availability_status': 'available', 'can_afford': True,
        'display_name': 'Rule', 'cost_type': 'actions', 'discovery_index': index, 'discovery_generation': 1,
        'target_set': target_set, **changes}


def discovery():
    return {'discovery_generation': 1, 'entity_uuid': UUID,
        'subjects': [{'uuid': UUID, 'kind': 'creature', 'name': 'Hero'},
                     {'uuid': OTHER, 'kind': 'object', 'name': 'Wall'}],
        'positions': [[-2, 3], [4, 5]],
        'target_sets': [
            [{'kind': 'subject', 'index': 0, 'subject': 0, 'position': 0, 'secondary_set': 1},
             {'kind': 'subject', 'index': 1, 'subject': 1, 'position': 1, 'secondary_set': 2},
             {'kind': 'subject', 'index': 2, 'subject': 0, 'secondary_set': 3}],
            [{'kind': 'subject', 'index': 3, 'subject': 1}],
            [{'kind': 'subject', 'index': 3, 'subject': 0}], [],
            [{'kind': 'self', 'index': 0}],
            [{'kind': 'subject', 'index': 0, 'subject': 0},
             {'kind': 'subject', 'index': 1, 'subject': 1}]],
        'entity_actions': [action(0, 0), action(1, 5)],
        'self_actions': [action(2, 4, 'self')],
        'object_actions': [action(3, 3, 'object', availability_status='source_unaffordable', can_afford=False)]}


def decoded(value, root='PlayerChoices'):
    return sdk.decode(root, json.dumps(value).encode())


def test_shared_options_preserve_branch_scope_repetition_self_and_omitted_defaults():
    value = decoded(discovery())
    before = deepcopy(value)
    chain, repeated, dash, unavailable = list(all_actions(value))
    first, second, empty = action_options(value, chain)
    assert secondary_options(value, chain, first)[0]['index'] == 3
    assert secondary_options(value, chain, second)[0]['index'] == 3
    assert binding_subject(value, secondary_options(value, chain, first)[0])['uuid'] == OTHER
    assert binding_subject(value, secondary_options(value, chain, second)[0])['uuid'] == UUID
    assert secondary_options(value, chain, empty) == []
    inherited = action_options(value, repeated)
    assert secondary_options(value, repeated, inherited[0]) is inherited
    assert selection_for(repeated, [inherited[0], inherited[1], inherited[0]])['target_indices'] == [0, 1, 0]
    self_option = action_options(value, dash)[0]
    assert binding_subject(value, self_option) is None and binding_position(value, self_option) is None
    assert selection_for(dash, [self_option])['target_indices'] == [0]
    assert action_options(value, unavailable) == []
    assert binding_value(first, 'is_path_hazardous') is False
    assert binding_value(first, 'path') is None
    assert binding_value(first, 'opportunity_attack_exposures') == []
    assert position_eligibility(value)[(-2, 3)][0] == (chain, first)
    assert value == before
    assert action_options(value, chain) is value['target_sets'][0]


@pytest.mark.parametrize('case', ['subject', 'position', 'path', 'exposure', 'secondary',
    'target_set', 'duplicate', 'nested', 'collision', 'available_empty', 'unavailable_nonempty',
    'source_affordable', 'other_unaffordable', 'duplicate_action', 'wrong_generation', 'wrong_ordinal'])
def test_malformed_compact_relations_are_rejected(case):
    value = discovery()
    primary = value['target_sets'][0][0]
    if case in ('subject', 'position', 'secondary'):
        primary[{'secondary': 'secondary_set'}.get(case, case)] = 999
    elif case == 'path':
        primary['path'] = [999]
    elif case == 'exposure':
        primary['opportunity_attack_exposures'] = [{'reactor_uuid': UUID,
            'reactor_name': 'Hero', 'from_position': 0, 'to_position': 999}]
    elif case == 'target_set':
        value['entity_actions'][0]['target_set'] = 999
    elif case == 'duplicate':
        value['target_sets'][0].append(dict(primary))
    elif case == 'nested':
        value['target_sets'][1][0]['secondary_set'] = 3
    elif case == 'collision':
        value['target_sets'][1][0]['index'] = 0
    elif case == 'available_empty':
        value['entity_actions'][0]['target_set'] = 3
    elif case == 'unavailable_nonempty':
        value['entity_actions'][0]['availability_status'] = 'no_valid_targets'
    elif case == 'source_affordable':
        value['object_actions'][0]['can_afford'] = True
    elif case == 'other_unaffordable':
        value['entity_actions'][0]['can_afford'] = False
    elif case == 'duplicate_action':
        value['self_actions'][0]['discovery_index'] = 0
    elif case == 'wrong_generation':
        value['entity_actions'][0]['discovery_generation'] = 2
    elif case == 'wrong_ordinal':
        value['entity_actions'][0]['discovery_index'] = 5
    with pytest.raises(sdk.ProtocolError):
        decoded(value)


@pytest.mark.parametrize('invalid', [True, '0', -1, 0.5, 1.0])
def test_references_are_not_coerced(invalid):
    value = discovery()
    value['target_sets'][0][0]['subject'] = invalid
    with pytest.raises(sdk.ProtocolError):
        decoded(value)


def test_preview_has_its_own_domains_and_distinguishes_deferred_from_computed_empty():
    choices = decoded(discovery())
    value = {'can_confirm': True, 'subjects': [{'uuid': OTHER, 'kind': 'object'}],
        'positions': [[99, -7]], 'target_sets': [[{'kind': 'subject', 'index': 3, 'subject': 0, 'position': 0}]],
        'next_target_set': 0, 'next_positions': [0], 'area_preview': 'computed'}
    result = decoded(value, 'PlayerSelectionPreview')
    binding = next_options(result)[0]
    assert binding_position(result, binding) == [99, -7]
    assert binding_subject(result, binding)['uuid'] == OTHER
    assert preview_positions(result) == ([99, -7],)
    assert preview_positions(result, affected=True) == ()
    assert choices['positions'][0] != binding_position(result, binding)
    assert result['area_preview'] == 'computed' and 'affected_positions' not in result
    assert decoded({**value, 'area_preview': 'deferred'}, 'PlayerSelectionPreview')['area_preview'] == 'deferred'
    for field in ('next_target_set', 'next_positions', 'affected_positions'):
        with pytest.raises(sdk.ProtocolError):
            decoded({**value, field: 999 if field == 'next_target_set' else [999]}, 'PlayerSelectionPreview')


def test_selected_paths_resolve_shared_positions_without_expanding_other_options():
    value = discovery()
    value['target_sets'][0][0].update(path=[0, 1], safe_path=[])
    result = decoded(value)
    target = action_options(result, next(all_actions(result)))[0]
    assert binding_path(result, target) == [[-2, 3], [4, 5]]
    assert binding_path(result, target, safe=True) == []
    assert binding_path(result, target)[0] is result['positions'][0]
