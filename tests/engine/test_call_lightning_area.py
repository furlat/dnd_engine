"""Public Call Lightning area, save, cost and concentration behavior."""
from dnd.core.dice import fixed_dice_faces
from dnd.entity import Entity
from dnd.spells.conjuration import CallLightning
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


def arena():
    reset_spell_regression_arena(24, 12)
    caster = create_spell_regression_actor('Storm caster', (2, 5), 'heroes', spell_slots={3: 2})
    targets = [create_spell_regression_actor(name, point, faction) for name, point, faction in (
        ('Center', (7, 5), 'monsters'), ('Neighbor', (8, 5), 'monsters'),
        ('Ally in area', (7, 6), 'heroes'), ('Outside', (10, 5), 'monsters'))]
    for target in targets:
        force_save_result(target, 'dexterity', succeeds=target is targets[1])
    Entity.update_all_entities_senses(max_distance=120)
    return caster, targets


def test_initial_and_repeat_strike_hit_every_area_occupant_once_and_preserve_outsider():
    caster, targets = arena()
    before = [target.get_normal_hp() for target in targets]
    with fixed_dice_faces(*([4] * 100)):
        cast = CallLightning(source_entity_uuid=caster.uuid, end_position=(7, 5), cast_at_level=3).apply()
    assert cast is not None and not cast.canceled
    after = [target.get_normal_hp() for target in targets]
    losses = [a-b for a,b in zip(before, after)]
    assert losses[0] > 0 and losses[1] == losses[0] // 2 and losses[2] == losses[0]
    assert losses[3] == 0
    assert cast.total_targets == 3
    assert len([action for action in caster.registered_actions if action.name == 'Call Lightning Strike']) == 1
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(*([4] * 100)):
        repeated = strike.instantiate(end_position=(7, 5)).apply()
    assert repeated is not None and not repeated.canceled
    assert [a-target.get_normal_hp() for a,target in zip(after, targets)] == losses
    assert caster.action_economy.actions.normalized_score == 0
    caster.remove_condition('Concentrating')
    assert caster.get_action_template('Call Lightning Strike') is None
    caster.action_economy.reset_all_costs()
    rejected = strike.instantiate(end_position=(7, 5)).apply()
    assert rejected is not None and rejected.canceled


def test_empty_initial_strike_still_grants_one_repeat_action():
    caster, targets = arena()
    before = [target.get_normal_hp() for target in targets]
    with fixed_dice_faces(*([4] * 100)):
        result = CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8), cast_at_level=3).apply()
    assert result is not None and not result.canceled
    assert [target.get_normal_hp() for target in targets] == before
    assert caster.get_action_template('Call Lightning Strike') is not None
    assert 'Concentrating' in caster.active_conditions
