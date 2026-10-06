"""Cold edits, native validation and physical party-screen acceptance."""

from dataclasses import replace

import pygame
import pytest

from dnd.content.characters.builds import resolve_character_build
from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS, FIGHTER_PREMADE_ID, SORCERER_PREMADE_ID, BARBARIAN_PREMADE_ID
from dnd.content.items.item_loadouts import CLASS_STARTING_LOADOUTS
from dnd.core.events import EventQueue
from game.character_select import choose_characters
from game.ui.character import CharacterDraft, CreatorHit, new_draft, edit_draft, draft_error, draw_creator, draw_appearance
from game.ui.layout import layout
from game.ui.primitives import fonts
from game.ui.skin import load_skin
from game.animation_data import load_animation_data
from game.ui_composition import compose_ui_media


@pytest.fixture(scope='module')
def assets():
    pygame.init();pygame.display.set_mode((1280,800))
    media=compose_ui_media();data=load_animation_data()
    yield media,data,load_skin(media.resources)
    pygame.quit()


@pytest.mark.parametrize('premade',(FIGHTER_PREMADE_ID,SORCERER_PREMADE_ID,BARBARIAN_PREMADE_ID))
def test_new_level_one_character_is_native_valid_and_does_not_create_events(premade,assets):
    start=EventQueue.event_cursor()
    draft=new_draft(premade)
    assert len(draft.build.class_levels)==1
    resolved=resolve_character_build(draft.build)
    assert resolved.build==draft.build and not draft_error(draft.build)
    assert EventQueue.event_cursor()==start


def test_point_buy_and_package_edits_are_cold_and_native_admission_explains_invalid_builds(assets):
    media,data,_=assets
    start=EventQueue.event_cursor()
    draft=new_draft(FIGHTER_PREMADE_ID)
    changed=edit_draft(draft,CreatorHit(pygame.Rect(0,0,1,1),'score',index=0,value='-1'),media,data)
    assert draft_error(changed.build) and not draft_error(draft.build)
    draft=replace(draft,page='Classes')
    opened=edit_draft(draft,CreatorHit(pygame.Rect(0,0,1,1),'choice',index=0),media,data)
    chosen=edit_draft(opened,CreatorHit(pygame.Rect(0,0,1,1),'value',value='starting_equipment.fighter.archery'),media,data)
    applied=edit_draft(chosen,CreatorHit(pygame.Rect(0,0,1,1),'apply'),media,data)
    resolve_character_build(applied.build)
    assert applied.build.item_loadout==CLASS_STARTING_LOADOUTS['starting_equipment.fighter.archery']
    assert EventQueue.event_cursor()==start


def test_every_creator_page_and_modular_appearance_uses_existing_media(assets):
    media,data,skin=assets
    screen=pygame.display.set_mode((1280,800))
    draft=CharacterDraft(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID])
    for page in ('Identity','Abilities','Classes','Appearance','Review'):
        hits,maximum=draw_creator(screen,layout(screen.size),fonts(1.),skin,media,data,{},(),replace(draft,page=page),'',(-1,-1))
        assert any(hit.verb=='save' and hit.enabled for hit in hits) and maximum>=0
    draw_appearance(screen,draft.build,data,{},pygame.Rect(940,270,140,220),100.)


def test_party_edit_cancellation_keeps_original_build_and_physical_start_is_cold(assets):
    media,data,skin=assets
    screen=pygame.display.set_mode((1280,800));geometry=layout(screen.size)
    party=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],PREMADE_CHARACTER_BUILDS[SORCERER_PREMADE_ID])
    roster,_=draw_creator(screen,geometry,fonts(1.),skin,media,data,{},party,None,'',(-1,-1))
    editor,_=draw_creator(screen,geometry,fonts(1.),skin,media,data,{},party,CharacterDraft(party[0]),'',(-1,-1))
    def click(hit):
        return tuple(pygame.event.Event(kind,button=1,pos=hit.rect.center)
                     for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP))
    start=EventQueue.event_cursor()
    result=choose_characters(max_frames=6,frame_events={
        1:click(next(hit for hit in roster if hit.verb=='edit' and hit.index==0)),
        2:click(next(hit for hit in editor if hit.verb=='cancel')),
        3:click(next(hit for hit in roster if hit.verb=='start'))})
    assert result==party and EventQueue.event_cursor()==start


def test_roster_changes_invalidate_old_clicks_in_the_same_sdl_batch(assets):
    pygame.init()
    media,data,skin=assets
    screen=pygame.display.set_mode((1280,800))
    party=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],PREMADE_CHARACTER_BUILDS[SORCERER_PREMADE_ID])
    roster,_=draw_creator(screen,layout(screen.size),fonts(1.),skin,media,data,{},party,None,'',(-1,-1))
    def click(verb,index=0):
        hit=next(hit for hit in roster if hit.verb==verb and hit.index==index)
        return tuple(pygame.event.Event(kind,button=1,pos=hit.rect.center)
                     for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP))
    start=EventQueue.event_cursor()
    # The second gesture refers to a party slot that no longer exists.
    result=choose_characters(max_frames=4,frame_events={
        1:click('remove')+click('edit',1),2:click('start')})
    assert result==(party[1],) and EventQueue.event_cursor()==start


def test_opening_editor_invalidates_previous_start_button(assets):
    pygame.init()
    media,data,skin=assets
    screen=pygame.display.set_mode((1280,800))
    party=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],PREMADE_CHARACTER_BUILDS[SORCERER_PREMADE_ID])
    roster,_=draw_creator(screen,layout(screen.size),fonts(1.),skin,media,data,{},party,None,'',(-1,-1))
    def click(verb):
        hit=next(hit for hit in roster if hit.verb==verb)
        return tuple(pygame.event.Event(kind,button=1,pos=hit.rect.center)
                     for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP))
    result=choose_characters(max_frames=3,frame_events={1:click('edit')+click('start')})
    assert result is None
