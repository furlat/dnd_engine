"""Physical SDL gestures respect modal capture and the native command boundary."""

import random

import pygame
import pytest
from dataclasses import replace

from game.encounter_play import run
from game.ui.action_bar import action_families, default_shortcuts
from game.ui.layout import layout
from game.player_facts import ActionFact
from game.controls import ActionSelection
from game.ui.combat_log import copy_log_selection, log_text_position
from game.ui.rich_text import plain_log
import game.encounter_play as encounter_play


@pytest.mark.parametrize('gesture',('click','press_escape_release','pause_space','menu_space','space'))
def test_one_physical_gesture_never_executes_behind_a_modal_or_pause(gesture):
    posted=False

    def input_events(state,available):
        nonlocal posted
        if posted:
            return None
        posted=True
        families=action_families(available)
        pins=default_shortcuts(available,families)
        offset=next(index for index,pin in enumerate(pins) if pin.behavior_id=='action.dodge')
        geometry=layout((1280,800))
        left=geometry.bar.centerx-(len(pins)+1)*geometry.slot//2
        point=(left+offset*geometry.slot+geometry.slot//2,geometry.bar.bottom-geometry.slot//2)
        press=pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point)
        release=pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=point)
        key=lambda key:pygame.event.Event(pygame.KEYDOWN,key=key,mod=0)
        events={'click':(press,release),'press_escape_release':(press,key(pygame.K_ESCAPE),release),
            'pause_space':(key(pygame.K_PAUSE),key(pygame.K_SPACE)),
            'menu_space':(key(pygame.K_ESCAPE),key(pygame.K_SPACE)),'space':(key(pygame.K_SPACE),)}[gesture]
        for event in events:
            pygame.event.post(event)
        return None

    state=random.getstate();random.seed(0)
    try:
        result=run(player_input=input_events,frame_deltas=(.1,),max_frames=150)
    finally:
        random.setstate(state)
    assert posted
    assert result.player_commands==(1 if gesture in ('click','space') else 0)
    if gesture=='click':
        assert any(isinstance(lineage.root.fact,ActionFact) and lineage.root.fact.behavior_id=='action.dodge' for lineage in result.lineages)


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
            expand=next(hit for hit in frame.hits if hit.verb=='log_expand' and hit.log_key==region.key)
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
        result=run(player_input=feed,frame_deltas=(.1,),max_frames=180)
    finally:
        random.setstate(state)
    assert phase==3 and copied==expected and len(copied)==2
    assert result.player_commands==1
