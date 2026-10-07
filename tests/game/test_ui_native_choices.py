"""Native alternatives remain reachable through compact presentation choices."""

import random
from dataclasses import replace

import pygame

import pytest

from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS, SORCERER_PREMADE_ID, FIGHTER_PREMADE_ID
from dnd.core.dice import fixed_dice_faces
from dnd.actions_functional import register_spell
from dnd.spells.walls import WallOfFire
from game.session import create_session, close_session, advance_controller, discover_player_actions, execute_player_action
from game.ui.action_bar import action_families, default_shortcuts, shortcut_indices, action_blocks, block_counts, draw_action_bar
from game.ui.layout import layout
from game.ui.primitives import fonts
from game.ui.skin import load_skin
from game.ui.hud import draw_hud
from game.ui.types import UIFocus
from game.controls import MenuState
from game.ui_composition import compose_ui_media
from game.presentation import capture_interval
from game.player_projection import project_sequence
from game.player_reduction import reduce_initialization
from game.replay import RecordedSequence
from dnd.core.events import EventQueue
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


def test_sorcery_conversions_expose_every_exact_native_level(session):
    actor=session.encounter.get_current_entity()
    choices=discover_player_actions(session,actor.uuid)
    families=action_families(choices)
    conversions=[family for family in families if family.key.behavior_id in (
        'action.class.sorcerer.convert_sorcery_points_to_slot','action.class.sorcerer.convert_slot_to_sorcery_points')]
    assert len(conversions)==2
    for family in conversions:
        selected=initial_variant(choices,family,None)
        options=variant_choices(choices,family,selected)
        assert all(group[0].dimension=='rank' for group in options)
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


def test_default_shortcuts_keep_known_spells_and_absent_pins_keep_their_position(session):
    actor=session.encounter.get_current_entity()
    choices=discover_player_actions(session,actor.uuid)
    families=action_families(choices)
    pins=default_shortcuts(choices,families)
    assert all(family.key in pins for family in families if choices.all_actions[family.indices[0]].is_spell and family.key.source_item_uuid is None)
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
        slot,target=next((row.weapon_slot,target.target_uuid) for row in choices.all_actions
                    if row.behavior_id=='action.attack' and row.weapon_slot in ('MELEE_MAIN','RANGED_MAIN')
                    for target in row.valid_targets if target.target_uuid is not None)
        for _ in range(2):
            choices=discover_player_actions(value,actor.uuid)
            command=main_attack(choices,target,slot)
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


def test_world_attack_never_changes_the_requested_weapon_slot():
    state=random.getstate();random.seed(0)
    value=create_session(player_builds=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],),enemy_positions=((14,10),(14,12)))
    try:
        for _ in range(32):
            if advance_controller(value).boundary.status=='waiting_for_human':
                break
        actor=value.encounter.get_current_entity()
        choices=discover_player_actions(value,actor.uuid)
        target=next(target.target_uuid for row in choices.all_actions
            if row.weapon_slot=='RANGED_MAIN' for target in row.valid_targets
            if target.target_uuid is not None and not any(candidate.target_uuid==target.target_uuid
                for melee in choices.all_actions if melee.weapon_slot=='MELEE_MAIN' for candidate in melee.valid_targets))
        assert main_attack(choices,target,'MELEE_MAIN') is None
        command=main_attack(choices,target,'RANGED_MAIN')
        assert command is not None and choices.all_actions[command.action_index].weapon_slot=='RANGED_MAIN'
    finally:
        close_session(value);random.setstate(state)


def test_live_bar_groups_owned_uses_and_wraps_without_losing_native_choices(session):
    actor=session.encounter.get_current_entity()
    choices=discover_player_actions(session,actor.uuid)
    initial=capture_interval(name='grouped bar',start_cursor=0,end_cursor=EventQueue.event_cursor(),
        observer_uuid=actor.uuid,battlefield_id=session.battlefield.definition.battlefield_id)
    state=reduce_initialization(project_sequence(RecordedSequence(initialization=initial,lineages=())).initialization)
    presented=state.actors[actor.uuid]
    families=action_families(choices);pins=default_shortcuts(choices,families)
    blocks=action_blocks(choices,families,pins,presented)
    assert all(block.families for block in blocks)
    rows=[[choices.all_actions[families[index].indices[0]] for index in block.families] for block in blocks]
    assert all(row.source_item_uuid is None and row.is_spell for row in rows[1])
    assert all(row.behavior_id.startswith('action.class.') for row in rows[2])
    assert all(row.source_item_uuid is not None and not row.is_attack for row in rows[3])
    assert all(row.interaction_affordance.surface!='world' for group in rows for row in group)
    removed=rows[3][0].source_item_uuid
    without=replace(presented,controlled_items=tuple(item for item in presented.controlled_items or () if item.item_uuid!=removed))
    updated=action_blocks(choices,families,pins,without)
    assert not any(families[index].key.source_item_uuid==removed for index in updated[3].families)
    assert updated[:3]==blocks[:3]
    pygame.init()
    try:
        pygame.display.set_mode((1,1))
        media=compose_ui_media();skin=load_skin(media.resources);images={}
        for size in ((1280,720),(1920,1080),(2560,1440)):
            for log_open in (False,True):
                geometry=layout(size,log_open=log_open,bar_counts=block_counts(blocks,presented))
                screen=pygame.Surface(size);font=fonts(geometry.scale)
                def draw(pages):
                    return draw_action_bar(screen,geometry,font,skin,media,images,choices,families,presented,
                        pages=pages,selected=None,ready=True,mouse=(-1,-1),shortcuts=pins)
                hits=draw((0,0,0,0));later=draw((0,1,0,0))
                assert {hit.bar_group for hit in hits if hit.verb=='family'}=={0,1,2,3}
                assert any(hit.shortcut is not None and hit.shortcut>=12 for hit in hits)
                assert all(geometry.bar.contains(hit.rect) for hit in hits)
                assert not geometry.bar.colliderect(geometry.log)
                assert geometry.bar==layout(size,log_open=not log_open,bar_counts=block_counts(blocks,presented)).bar
                keys=[hit.shortcut for hit in hits if hit.shortcut is not None]
                assert len(keys)==len(set(keys))
                assert all(not a.rect.colliderect(b.rect) for i,a in enumerate(hits) for b in hits[i+1:])
                assert [(h.verb,h.index,h.rect) for h in hits if h.bar_group!=1]==[(h.verb,h.index,h.rect) for h in later if h.bar_group!=1]
                # Cycling every spell page reaches every exact family once.
                seen=set()
                for page in range(len(blocks[1].families)):
                    seen.update(hit.index for hit in draw((0,page,0,0)) if hit.verb=='family' and hit.bar_group==1)
                assert seen==set(blocks[1].families)
        for size,scale in (((960,540),1.),((1280,720),1.5)):
            geometry=layout(size,scale,bar_counts=block_counts(blocks,presented))
            frame=draw_hud(pygame.Surface(size),geometry,fonts(geometry.scale),skin,media,images,state,None,
                choices,families,MenuState(),UIFocus(panel='menu'),None,ready=True,mouse=(-1,-1),
                status='',shown_hp={},shortcuts=pins)
            assert len(frame.hits)==9
            assert all(geometry.viewport.contains(hit.rect) for hit in frame.hits)
    finally:
        pygame.quit()
