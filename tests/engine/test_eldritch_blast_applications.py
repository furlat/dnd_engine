"""One cast allocates and resolves real independent beams through native discovery."""

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.entity import Entity
from dnd.spells.evocation import EldritchBlast
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


def cast_beams(level: int, split: bool, dice: tuple[int, ...]):
    reset_spell_regression_arena(12, 8)
    caster = create_spell_regression_actor('Caster', (2, 2), 'heroes')
    first = create_spell_regression_actor('First', (6, 2), 'enemies')
    second = create_spell_regression_actor('Second', (6, 3), 'enemies')
    register_spell(caster, EldritchBlast, caster_level=level)
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    action = next(row for row in available.all_actions if row.behavior_id == 'spell.eldritch_blast')
    count = 1 + int(level >= 5) + int(level >= 11) + int(level >= 17)
    identities = tuple(second.uuid if split and index % 2 else first.uuid for index in range(count))
    target = next(row for row in action.valid_targets if row.target_uuid == identities[0])
    cursor = EventQueue.event_cursor()
    hp = {first.uuid: first.get_hp(), second.uuid: second.get_hp()}
    with fixed_dice_faces(*dice):
        result = execute_available_action(caster, action, target,
                                         extra_target_uuids=[str(uid) for uid in identities[1:]])
    events = tuple(e for _, e in EventQueue.iter_events_since(cursor) if e.phase is EventPhase.COMPLETION)
    return caster, (first, second), hp, identities, action, result, events


@pytest.mark.parametrize(('level', 'count'), ((1, 1), (5, 2), (11, 3), (17, 4)))
@pytest.mark.parametrize('split', (False, True))
def test_beams_keep_individual_applications_and_pay_one_action(level, count, split) -> None:
    caster, targets, hp, identities, action, result, events = cast_beams(level, split, (15, 4) * count)
    assert result is not None and not result.canceled
    assert action.outcome_profile is not None
    assert action.outcome_profile.applications == count
    assert action.outcome_profile.damage_rolls[0].dice_count == 1
    beams = [e for e in events if isinstance(e, SpellEvent) and e.application_id is not None]
    assert [e.target_entity_uuid for e in beams] == list(identities)
    assert [e.application_index for e in beams] == list(range(count))
    assert len({e.application_id for e in beams}) == count
    assert all(e.attack_outcome is AttackOutcome.HIT for e in beams)
    assert all(e.damage_rolls and e.damage_rolls[0].total == 4 for e in beams)
    assert caster.action_economy.actions.normalized_score == 0
    assert {t.uuid: hp[t.uuid] - t.get_hp() for t in targets} == {
        t.uuid: identities.count(t.uuid) * 4 for t in targets}
    assert len([e for e in events if isinstance(e, DamageAppliedEvent)]) == count


def test_hit_miss_and_critical_are_separate_beam_results() -> None:
    _, targets, hp, _, _, result, events = cast_beams(11, True, (15, 4, 1, 20, 3, 5))
    assert result is not None and not result.canceled
    beams = [e for e in events if isinstance(e, SpellEvent) and e.application_id is not None]
    assert [e.attack_outcome for e in beams] == [AttackOutcome.HIT, AttackOutcome.CRIT_MISS, AttackOutcome.CRIT]
    assert hp[targets[0].uuid] - targets[0].get_hp() == 12
    assert hp[targets[1].uuid] == targets[1].get_hp()
    assert len([e for e in events if isinstance(e, DamageAppliedEvent)]) == 2
