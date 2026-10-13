"""Lookups over response-local choices; no game rules or target-tree expansion."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from . import contracts as c


class ProtocolError(Exception):
    pass


type ChoiceOption = c.SubjectBinding | c.PositionBinding | c.SelfBinding
type ChoiceDomains = c.PlayerChoices | c.PlayerSelectionPreview


def all_actions(choices: c.PlayerChoices) -> Iterator[c.PlayerAction]:
    """Yield native rows in their original discovery order, without copying."""
    for group in ('entity_actions', 'position_actions', 'self_actions', 'object_actions'):
        yield from choices.get(group, ())


def _at(values: Sequence, index: int, field: str):
    if type(index) is not int or not 0 <= index < len(values):
        raise ProtocolError(f'{field}: reference {index} is out of range')
    return values[index]


def action_options(choices: c.PlayerChoices, action: c.PlayerAction) -> Sequence[ChoiceOption]:
    """Return the shared primary set; indices remain native selection indices."""
    return _at(choices.get('target_sets', ()), action['target_set'], 'target_set')


def binding_subject(domains: ChoiceDomains, binding: ChoiceOption) -> c.ChoiceSubject | None:
    return (_at(domains.get('subjects', ()), binding['subject'], 'subject')
            if binding['kind'] == 'subject' else None)


def binding_position(domains: ChoiceDomains, binding: ChoiceOption) -> Sequence[int] | None:
    if binding['kind'] == 'self' or binding.get('position') is None:
        return None
    return _at(domains.get('positions', ()), binding['position'], 'position')


def binding_value(binding: ChoiceOption, field: str) -> Any:
    """Read documented pair-data defaults without adding fields to the binding."""
    if field in binding:
        return binding[field]
    if field == 'is_path_hazardous':
        return False
    if field in ('opportunity_attack_exposures', 'safe_path_opportunity_attack_exposures'):
        return []
    if field in ('distance', 'path_cost', 'extra_target_uuids', 'secondary_set',
                 'safe_path_cost', 'path', 'safe_path', 'position'):
        return None
    raise KeyError(field)


def binding_path(domains: ChoiceDomains, binding: ChoiceOption, *, safe: bool = False) -> list | None:
    references = binding_value(binding, 'safe_path' if safe else 'path')
    if references is None:
        return None
    return [_at(domains.get('positions', ()), index, 'path') for index in references]


def secondary_options(choices: c.PlayerChoices, action: c.PlayerAction,
                      primary: ChoiceOption) -> Sequence[ChoiceOption]:
    reference = primary.get('secondary_set')
    return (action_options(choices, action) if reference is None else
            _at(choices.get('target_sets', ()), reference, 'secondary_set'))


def next_options(preview: c.PlayerSelectionPreview) -> Sequence[ChoiceOption]:
    return _at(preview.get('target_sets', ()), preview['next_target_set'], 'next_target_set')


def preview_positions(preview: c.PlayerSelectionPreview, *, affected: bool = False) -> tuple:
    field = 'affected_positions' if affected else 'next_positions'
    return tuple(_at(preview.get('positions', ()), index, field)
                 for index in preview.get(field, ()))


def selection_for(action: c.PlayerAction, targets: Sequence[ChoiceOption], *,
                  extra_target_positions: Sequence[Sequence[int]] = (),
                  prefer_safe: bool = True) -> c.ActionSelection:
    """Construct an ordered command prefix, preserving repeats and native indices."""
    return {'action_index': action.get('discovery_index', 0),
            'target_indices': [target['index'] for target in targets],
            'extra_target_positions': [list(position) for position in extra_target_positions],
            'prefer_safe': prefer_safe}


def position_eligibility(choices: c.PlayerChoices) -> dict[tuple[int, int], list[tuple]]:
    """Build a requested inverse of primary bindings, retaining subject identities."""
    result: dict[tuple[int, int], list[tuple]] = {}
    for action in all_actions(choices):
        for binding in action_options(choices, action):
            position = binding_position(choices, binding)
            if position is not None:
                result.setdefault(tuple(position), []).append((action, binding))
    return result


def _check_domains(domains: ChoiceDomains) -> None:
    positions = domains.get('positions', ())
    subjects = domains.get('subjects', ())
    sets = domains.get('target_sets', ())
    indices: list[set[int]] = []
    secondary_sets: set[int] = set()
    for targets in sets:
        seen: set[int] = set()
        for binding in targets:
            if (type(binding['index']) is not int or not 0 <= binding['index'] <= (1 << 53) - 1
                    or binding['index'] in seen):
                raise ProtocolError('Invalid or duplicate target index within a target set')
            seen.add(binding['index'])
            if binding['kind'] == 'subject':
                _at(subjects, binding['subject'], 'subject')
            if binding['kind'] != 'self' and binding.get('position') is not None:
                _at(positions, binding['position'], 'position')
            for field in ('path', 'safe_path'):
                for reference in binding.get(field) or ():
                    _at(positions, reference, field)
            for field in ('opportunity_attack_exposures', 'safe_path_opportunity_attack_exposures'):
                for exposure in binding.get(field, ()):
                    _at(positions, exposure['from_position'], field)
                    _at(positions, exposure['to_position'], field)
            reference = binding.get('secondary_set')
            if reference is not None:
                _at(sets, reference, 'secondary_set')
                secondary_sets.add(reference)
        indices.append(seen)
    # Each secondary set is checked once, regardless of how many primaries share it.
    for reference in secondary_sets:
        if any(binding.get('secondary_set') is not None for binding in sets[reference]):
            raise ProtocolError('Secondary options cannot contain secondary overrides')
    for targets in sets:
        for primary in targets:
            reference = primary.get('secondary_set')
            if reference is not None and primary['index'] in indices[reference]:
                raise ProtocolError('Secondary target index collides with its primary')


def check_choices(choices: c.PlayerChoices) -> None:
    _check_domains(choices)
    sets = choices.get('target_sets', ())
    for ordinal, action in enumerate(all_actions(choices)):
        index = action.get('discovery_index', 0)
        if type(index) is not int or index != ordinal:
            raise ProtocolError('Discovery action index does not match its ordinal')
        if action.get('discovery_generation', 0) != choices['discovery_generation']:
            raise ProtocolError('Action belongs to a different discovery generation')
        targets = _at(sets, action['target_set'], 'target_set')
        if (action['availability_status'] == 'source_unaffordable') == action['can_afford']:
            raise ProtocolError('Contradictory source affordability')
        if (action['availability_status'] == 'available') != bool(targets):
            raise ProtocolError('Contradictory action availability and target set')


def check_preview(preview: c.PlayerSelectionPreview) -> None:
    _check_domains(preview)
    next_options(preview)
    positions = preview.get('positions', ())
    for field in ('next_positions', 'affected_positions'):
        for reference in preview.get(field, ()):
            _at(positions, reference, field)
