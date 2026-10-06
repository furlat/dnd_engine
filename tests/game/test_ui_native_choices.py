"""Native alternatives remain reachable through compact presentation choices."""

import random

import pytest

from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS, SORCERER_PREMADE_ID, FIGHTER_PREMADE_ID
from dnd.core.dice import fixed_dice_faces
from dnd.actions_functional import register_spell
from dnd.spells.walls import WallOfFire
from game.session import create_session, close_session, advance_controller, discover_player_actions, execute_player_action
from game.ui.action_bar import action_families, default_shortcuts, shortcut_indices
from game.ui.variants import initial_variant, variant_choices, variant_values
from game.ui.world_interaction import main_attack
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.fixture
def session():
    state=random.getstate();random.seed(0)
    value=create_session(player_builds=(PREMADE_CHARACTER_BUILDS[SORCERER_PREMADE_ID],))
    try:
        for _ in range(32):
            if advance_controller(value).boundary.status=='waiting_for_human':
                break
        yield value
    finally:
        close_session(value);random.setstate(state)


def test_sorcery_conversions_without_facets_expose_every_exact_native_option(session):
    actor=session.encounter.get_current_entity()
    choices=discover_player_actions(session,actor.uuid)
    families=action_families(choices)
    conversions=[family for family in families if family.key.behavior_id in (
        'action.class.sorcerer.convert_sorcery_points_to_slot','action.class.sorcerer.convert_slot_to_sorcery_points')]
    assert len(conversions)==2
    for family in conversions:
        selected=initial_variant(choices,family,None)
        options=variant_choices(choices,family,selected)
        assert {option.row_index for group in options for option in group}==set(family.indices)
        assert len(family.indices)>1


def test_straight_fire_wall_has_no_side_picker_and_rings_keep_native_sides():
    reset_spell_regression_arena(12,12)
    actor=create_spell_regression_actor('Caster',(1,1),'heroes',spell_slots={4:2})
    register_spell(actor,WallOfFire)
    choices=actor.get_available_actions()
    family=next(family for family in action_families(choices) if family.key.behavior_id=='spell.wall_of_fire')
    straight=next(index for index in family.indices if variant_values(choices.all_actions[index])['form']=='segment')
    groups=variant_choices(choices,family,straight)
    assert not any(group[0].dimension=='side' for group in groups)
    assert {choice.value for group in groups if group[0].dimension=='form' for choice in group}=={'segment','ring'}
    ring=next(index for index in family.indices if variant_values(choices.all_actions[index])['form']=='ring')
    groups=variant_choices(choices,family,ring)
    assert {choice.value for group in groups if group[0].dimension=='side' for choice in group}=={'inside','outside'}


def test_default_shortcuts_are_small_and_absent_pins_keep_their_position(session):
    actor=session.encounter.get_current_entity()
    choices=discover_player_actions(session,actor.uuid)
    families=action_families(choices)
    pins=default_shortcuts(choices,families)
    assert len(pins)<=10
    assert all(pin.behavior_id not in ('action.move','action.attack','action.feature.extra_attack','action.core.drop') for pin in pins)
    removed=tuple(family for family in families if family.key!=pins[0])
    indices=shortcut_indices(removed,pins)
    assert len(indices)==len(pins) and indices[0] is None
    assert tuple(removed[index].key for index in indices[1:] if index is not None)==pins[1:]
    drops=[row for row in choices.all_actions if row.behavior_id=='action.core.drop']
    assert drops and all(row.interaction_affordance.surface=='inventory' for row in drops)


def test_click_attack_uses_extra_attack_after_the_normal_attack_without_spending_bonus():
    state=random.getstate();random.seed(0)
    value=create_session(player_builds=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],),enemy_positions=((11,10),(11,12)))
    try:
        for _ in range(32):
            if advance_controller(value).boundary.status=='waiting_for_human':
                break
        actor=value.encounter.get_current_entity()
        choices=discover_player_actions(value,actor.uuid)
        target=next(target.target_uuid for row in choices.all_actions
                    if row.behavior_id=='action.attack' and row.weapon_slot in ('MELEE_MAIN','RANGED_MAIN')
                    for target in row.valid_targets if target.target_uuid is not None)
        for _ in range(2):
            choices=discover_player_actions(value,actor.uuid)
            command=main_attack(choices,target)
            assert command is not None
            row=choices.all_actions[command.action_index]
            recipient=next(target for target in row.valid_targets if target.index==command.target_indices[0])
            assert row.cost_type!='bonus_actions'
            with fixed_dice_faces(*([1]*100)):
                execute_player_action(value,actor.uuid,row,recipient)
        assert row.behavior_id=='action.feature.extra_attack'
        assert actor.action_economy.bonus_actions.normalized_score==1
    finally:
        close_session(value);random.setstate(state)
