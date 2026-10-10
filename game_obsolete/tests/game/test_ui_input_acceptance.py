"""Physical SDL gestures respect modal capture and the native command boundary."""

import random

import pygame
import pytest
from dataclasses import replace

from game.encounter_play import run
from game.ui.action_bar import action_families, default_shortcuts
from game.ui.layout import layout
from dnd.player.facts import ActionFact
from game.controls import ActionSelection
from game.interaction_frame import pick_world
from game.ui.combat_log import copy_log_selection, log_text_position
from game.ui.rich_text import plain_log
from dnd.core.equipment_types import BodyPart
import game.encounter_play as encounter_play


@pytest.mark.parametrize('gesture',('click','press_escape_release','pause_space','menu_space','space','hotkey','shift_hotkey'))
def test_one_physical_gesture_never_executes_behind_a_modal_or_pause(gesture,monkeypatch):
    posted=False
    drawn=[]
    original=encounter_play.draw_hud
    def observe(*args,**kwargs):
        frame=original(*args,**kwargs);drawn.append(frame);return frame
    monkeypatch.setattr(encounter_play,'draw_hud',observe)

    def input_events(state,available):
        nonlocal posted
        if posted or not drawn:
            return None
        posted=True
        hit=next((hit for hit in drawn[-1].hits if hit.family_key is not None
            and hit.family_key.behavior_id in (('action.dodge','action.disengage') if gesture=='shift_hotkey' else ('action.dodge',))
            and (gesture!='shift_hotkey' or hit.shortcut is not None and hit.shortcut>=12)),None)
        if hit is None:
            posted=False
            return None
        point=hit.rect.center
        press=pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point)
        release=pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=point)
        key=lambda key:pygame.event.Event(pygame.KEYDOWN,key=key,mod=0)
        hotkeys=(pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4,pygame.K_5,pygame.K_6,pygame.K_7,pygame.K_8,pygame.K_9,pygame.K_0,pygame.K_MINUS,pygame.K_EQUALS)
        shortcut=hit.shortcut or 0
        events={'hotkey':(pygame.event.Event(pygame.KEYDOWN,key=hotkeys[shortcut%12],mod=pygame.KMOD_SHIFT if shortcut>=12 else 0),),
            'shift_hotkey':(pygame.event.Event(pygame.KEYDOWN,key=hotkeys[shortcut%12],mod=pygame.KMOD_SHIFT),),'click':(press,release),'press_escape_release':(press,key(pygame.K_ESCAPE),release),
            'pause_space':(key(pygame.K_PAUSE),key(pygame.K_SPACE)),
            'menu_space':(key(pygame.K_ESCAPE),key(pygame.K_SPACE)),'space':(key(pygame.K_SPACE),)}[gesture]
        for event in events:
            pygame.event.post(event)
        return None

    state=random.getstate();random.seed(0)
    try:
        result=run(test_seed=0, player_input=input_events,frame_deltas=(.1,),max_frames=150)
    finally:
        random.setstate(state)
    assert posted
    assert result.player_commands==(1 if gesture in ('click','space','hotkey','shift_hotkey') else 0)
    if gesture in ('click','hotkey','shift_hotkey'):
        assert any(isinstance(lineage.root.fact,ActionFact) and lineage.root.fact.behavior_id in ('action.dodge','action.disengage') for lineage in result.lineages)


def test_batched_log_expansion_rejects_old_text_coordinates_and_new_drag_copies_displayed_text(monkeypatch):
    # Observe the real draw boundary to aim physical gestures at visible text.
    # The wrapper does not replace wording, layout, events or rendering.
    drawn=[];copied=[];expected=[];phase=-1
    original=encounter_play.draw_combat_log
    def observe(*args,**kwargs):
        frame,view=original(*args,**kwargs)
        drawn.append((frame,args[4],view,args[6]))
        return frame,view
    monkeypatch.setattr(encounter_play,'draw_combat_log',observe)
    monkeypatch.setattr(pygame.scrap,'put_text',copied.append)
    def click(point):
        return tuple(pygame.event.Event(kind,button=1,pos=point)
            for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP))
    def feed(state,available):
        nonlocal phase
        if phase==-1:
            index,row=next((index,row) for index,row in enumerate(available.all_actions)
                if row.behavior_id=='action.move' and row.valid_targets)
            destination=min((target for target in row.valid_targets if target.path_cost),key=lambda target:target.path_cost)
            phase=0
            return ActionSelection(index,(destination.index,))
        if phase==0:
            events=click((1240,27));phase=1
        elif phase==1 and drawn:
            frame,history,view,cache=drawn[-1]
            region=next(region for region in cache.text_regions
                if len(region.advances)>6 and any(row.key==region.key and row.entry.compact!=row.entry.verbose for row in history.rows))
            expand=next(hit for hit in frame.hits if hit.verb=='log_row_detail' and hit.log_key==region.key)
            row=next(row for row in history.rows if row.key==region.key)
            expected.append(plain_log(row.entry.detailed))
            start=(region.rect.left+region.advances[1],region.rect.centery)
            end=(region.rect.left+region.advances[6],region.rect.centery)
            events=(*click(expand.rect.center),pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=start),
                pygame.event.Event(pygame.MOUSEMOTION,pos=end,rel=(0,0),buttons=(1,0,0)),
                pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=end),
                pygame.event.Event(pygame.KEYDOWN,key=pygame.K_c,mod=pygame.KMOD_CTRL))
            phase=2
        elif phase==2 and len(copied)==1:
            _,history,view,cache=drawn[-1]
            region=next(region for region in cache.text_regions if len(region.advances)>6)
            start=(region.rect.left+region.advances[1],region.rect.centery)
            end=(region.rect.left+region.advances[6],region.rect.centery)
            anchor=log_text_position(cache,start);endpoint=log_text_position(cache,end,region.key)
            assert anchor is not None and endpoint is not None
            expected.append(copy_log_selection(history,replace(view,selected=region.key,selection_anchor=anchor,selection_end=endpoint[1])))
            events=(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=start),
                pygame.event.Event(pygame.MOUSEMOTION,pos=end,rel=(0,0),buttons=(1,0,0)),
                pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=end),
                pygame.event.Event(pygame.KEYDOWN,key=pygame.K_c,mod=pygame.KMOD_CTRL))
            phase=3
        else:
            return None
        for event in events:
            pygame.event.post(event)
        return None
    state=random.getstate();random.seed(0)
    try:
        result=run(test_seed=0, player_input=feed,frame_deltas=(.1,),max_frames=180)
    finally:
        random.setstate(state)
    assert phase==3 and copied==expected and len(copied)==2
    assert result.player_commands==1


def test_attack_commit_clears_hover_outline_through_the_animation(monkeypatch):
    pointer=[(0,0)];drawn=[];phase=0;subject=None
    original=encounter_play.draw_highlights
    def observe(screen,interaction,highlights):
        drawn.append((interaction,tuple(highlights)))
        return original(screen,interaction,highlights)
    monkeypatch.setattr(encounter_play,'draw_highlights',observe)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:pointer[0])
    def feed(state,actions):
        nonlocal phase,subject
        if not drawn or phase==3:
            return None
        if phase==0:
            candidate=next(((i,row,target) for i,row in enumerate(actions.all_actions)
                if row.behavior_id=='spell.magic_missile' and row.cast_at_level==1
                for target in row.valid_targets if target.target_uuid is not None and state.actors[target.target_uuid].creature_content_ref is not None),None)
            if candidate is None:return None
            index,row,target=candidate;subject=target.target_uuid
            region=next((r for r in drawn[-1][0].regions if r.hit.identity==str(subject)),None)
            if region is None:return None
            xs,ys=region.mask.nonzero()
            points=((region.destination[0]+int(x),region.destination[1]+int(y)) for x,y in zip(xs,ys,strict=True))
            point=min((point for point in points if point[1]<500 and (hit:=pick_world(drawn[-1][0],point)) is not None and hit.identity==str(subject)),
                key=lambda p:abs(p[0]-region.destination[0]-region.mask.shape[0]/2)+abs(p[1]-region.destination[1]-region.mask.shape[1]/2),default=None)
            if point is None:return None
            pointer[0]=point
            phase=1;return None
        if phase==1:
            phase=2 if any(hit.identity==str(subject) for hit,_ in drawn[-1][1]) else 0
            return None
        if phase==2:
            index,row=next((i,row) for i,row in enumerate(actions.all_actions) if row.behavior_id=='spell.magic_missile' and row.cast_at_level==1)
            target=next(t for t in row.valid_targets if t.target_uuid==subject)
            phase=3;return ActionSelection(index,(target.index,)*row.num_projectiles)
        return None
    state=random.getstate();random.seed(0)
    try:
        result=run(test_seed=0, player_input=feed,frame_deltas=(.1,),max_frames=90,collect_frames=True)
    finally:random.setstate(state)
    assert phase==3 and result.player_commands==1
    assert any(highlights for _,highlights in drawn)
    assert any(frame.root_uuid is not None for frame in result.frames)
    assert len(result.frames)==len(drawn)
    assert all(not highlights for frame,(_,highlights) in zip(result.frames,drawn,strict=True)
               if frame.root_uuid is not None or frame.pending)


def test_hover_equipment_slot_then_click_replacement_equips_the_owned_item(monkeypatch):
    drawn=[];pointer=[(-1,-1)];phase=0;expected=None;owner=None
    original=encounter_play.draw_hud
    def observe(*args,**kwargs):
        frame=original(*args,**kwargs);drawn.append(frame);return frame
    monkeypatch.setattr(encounter_play,'draw_hud',observe)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:pointer[0])
    def feed(state,available):
        nonlocal phase,expected,owner
        if phase==0:
            owner=available.entity_uuid
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_i,mod=0))
            phase=1
        elif phase==1 and drawn:
            hit=next((h for h in drawn[-1].hits if h.verb=='equipment_slot' and h.equipment_slot==BodyPart.BODY),None)
            if hit is not None:
                pointer[0]=hit.rect.center;phase=2
        elif phase==2 and drawn:
            hit=next((h for h in drawn[-1].hits if h.verb=='equip' and h.equipment_slot==BodyPart.BODY and h.enabled),None)
            if hit is not None:
                assert owner is not None
                expected=hit.identity
                assert any(item.item_uuid==expected for item in state.actors[owner].controlled_items or ())
                pointer[0]=hit.rect.center
                for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
                    pygame.event.post(pygame.event.Event(kind,button=1,pos=hit.rect.center))
                phase=3
        elif phase==3 and owner is not None and any(layer.slot==BodyPart.BODY.value and layer.item_uuid==expected
                for layer in state.actors[owner].visual_loadout.layers):
            pygame.event.post(pygame.event.Event(pygame.QUIT));phase=4
        return None
    state=random.getstate();random.seed(0)
    try:
        result=run(test_seed=0, encounter_id='encounter.lantern_crypt',player_input=feed,frame_deltas=(.1,),max_frames=90)
    finally:random.setstate(state)
    assert phase==4 and expected is not None and result.player_commands==1
    assert not result.presentation_gaps


@pytest.mark.parametrize('behavior',('spell.burning_hands','action.class.sorcerer.convert_sorcery_points_to_slot'))
def test_hover_choices_use_bar_sized_level_icons_and_click_selects_native_level(behavior,monkeypatch):
    drawn=[];pointer=[(-1,-1)];phase=0;source=None;selected=None
    original=encounter_play.draw_hud
    def observe(*args,**kwargs):
        frame=original(*args,**kwargs);drawn.append((frame,args[8],args[10]));return frame
    monkeypatch.setattr(encounter_play,'draw_hud',observe)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:pointer[0])
    def feed(state,available):
        nonlocal phase,source,selected
        if not drawn:return None
        frame,choices,menu=drawn[-1]
        if phase==0:
            hit=next((h for h in frame.hits if h.verb=='family' and h.family_key and h.family_key.behavior_id==behavior),None)
            if hit:
                source=hit.rect;pointer[0]=hit.rect.center;phase=1
        elif phase==1 and choices is not None:
            options=[h for h in frame.hits if h.verb=='variant']
            if not options:return None
            assert source is not None and all(h.rect.size==source.size and h.rect.bottom<source.top for h in options)
            selected=next(h for h in options if choices.all_actions[h.index].cast_at_level==2 or
                any(f.key=='rank' and f.value=='2' for f in choices.all_actions[h.index].variant_facets))
            pointer[0]=selected.rect.center;phase=2
        elif phase==2:
            assert selected is not None and any(h.rect==selected.rect and h.index==selected.index for h in frame.hits if h.verb=='variant')
            for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
                pygame.event.post(pygame.event.Event(kind,button=1,pos=selected.rect.center))
            phase=3
        elif phase==3:
            if behavior.startswith('spell.'):
                if not menu.active:return None
                assert choices is not None and choices.all_actions[menu.selected_action].cast_at_level==2
            pygame.event.post(pygame.event.Event(pygame.QUIT));phase=4
        return None
    state=random.getstate();random.seed(0)
    try:
        result=run(test_seed=0, encounter_id='encounter.lantern_crypt',player_input=feed,frame_deltas=(.1,),max_frames=120)
    finally:random.setstate(state)
    assert phase==4
    assert result.player_commands==(0 if behavior.startswith('spell.') else 1)
    if not behavior.startswith('spell.'):
        assert any(isinstance(lineage.root.fact,ActionFact) and lineage.root.fact.behavior_id==behavior for lineage in result.lineages)
