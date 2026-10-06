"""Pre-encounter composition screen using cold native builds and choices."""

from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

import pygame

from dnd.content.characters.builds import CharacterBuild
from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS, FIGHTER_PREMADE_ID, SORCERER_PREMADE_ID
from dnd.types.character_progression import CharacterClass
from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows
from game.ui.character import CharacterDraft, CreatorHit, draw_creator, draw_appearance, draft_error, edit_draft, new_draft
from game.ui.layout import layout
from game.ui.primitives import fonts, text, MUTED
from game.ui.skin import load_skin
from game.ui_composition import compose_ui_media


def choose_characters(*, window_size: tuple[int,int]=(1280,800), fullscreen: bool=False,
                      frame_events: Mapping[int,Sequence[pygame.event.Event]] | None=None,
                      max_frames: int|None=None, capture_dir: Path|None=None) -> tuple[CharacterBuild,...]|None:
    pygame.init()
    screen=pygame.display.set_mode((0,0) if fullscreen else window_size,
                                  pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
    pygame.display.set_caption('D&D Engine — Create your party')
    media=compose_ui_media();skin=load_skin(media.resources);data=load_animation_data()
    images: dict[tuple[str,tuple[int,int]],pygame.Surface]={}
    bodies: LoadedBodyRows={}
    party=(PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],PREMADE_CHARACTER_BUILDS[SORCERER_PREMADE_ID])
    draft: CharacterDraft|None=None
    editing_index: int|None=None
    captured: CreatorHit|None=None
    hits: tuple[CreatorHit,...]=()
    status='';frame=0;clock=pygame.time.Clock()
    windowed_size=window_size
    if capture_dir is not None:
        capture_dir.mkdir(parents=True,exist_ok=True)
    try:
        while max_frames is None or frame<max_frames:
            for event in (frame_events or {}).get(frame,()):
                pygame.event.post(event)
            for event in pygame.event.get():
                if event.type==pygame.QUIT:
                    return None
                if event.type==pygame.WINDOWRESIZED:
                    screen=pygame.display.set_mode((event.x,event.y),pygame.RESIZABLE)
                    captured=None
                    hits=()
                elif event.type==pygame.KEYDOWN:
                    captured=None
                    hits=()
                    if event.key==pygame.K_RETURN and event.mod&pygame.KMOD_ALT:
                        if not fullscreen:
                            windowed_size=screen.size
                        fullscreen=not fullscreen
                        screen=pygame.display.set_mode((0,0) if fullscreen else windowed_size,
                                                      pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
                    elif event.key==pygame.K_ESCAPE:
                        if draft is not None and draft.choice is not None:
                            draft=replace(draft,choice=None,search='',scroll=0)
                        elif draft is not None:
                            draft=None;editing_index=None
                        else:
                            return None
                    elif draft is not None and event.key==pygame.K_BACKSPACE:
                        if draft.choice is not None:
                            draft=replace(draft,search=draft.search[:-1],scroll=0)
                        elif draft.editing_name:
                            draft=replace(draft,build=replace(draft.build,name=draft.build.name[:-1]))
                    elif draft is not None and event.key==pygame.K_RETURN:
                        draft=replace(draft,editing_name=False)
                elif event.type==pygame.TEXTINPUT and draft is not None:
                    captured=None
                    hits=()
                    if draft.choice is not None:
                        draft=replace(draft,search=(draft.search+event.text)[:80],scroll=0)
                    elif draft.editing_name:
                        draft=replace(draft,build=replace(draft.build,name=(draft.build.name+event.text)[:80]))
                elif event.type==pygame.MOUSEWHEEL and draft is not None:
                    captured=None
                    hits=()
                    draft=replace(draft,scroll=max(0,draft.scroll-event.y*round(48*layout(screen.size).scale)))
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                    captured=next((hit for hit in reversed(hits) if hit.rect.collidepoint(event.pos)),None)
                elif event.type==pygame.MOUSEBUTTONUP and event.button==1:
                    hit=captured;captured=None
                    if hit is None or not hit.enabled or not hit.rect.collidepoint(event.pos):
                        continue
                    # Every hit belongs to the last rendered party/draft. A
                    # committed gesture invalidates that surface until redraw.
                    hits=()
                    if hit.verb=='quit':
                        return None
                    if hit.verb=='start':
                        status=next((error for build in party if (error:=draft_error(build))), '')
                        if not status:
                            return party
                    elif hit.verb=='premade':
                        keys=tuple(PREMADE_CHARACTER_BUILDS)
                        current=next((index for index,key in enumerate(keys) if PREMADE_CHARACTER_BUILDS[key]==party[hit.index]),-1)
                        values=list(party);values[hit.index]=PREMADE_CHARACTER_BUILDS[keys[(current+1)%len(keys)]];party=tuple(values)
                    elif hit.verb=='remove' and len(party)>1:
                        party=tuple(build for index,build in enumerate(party) if index!=hit.index)
                    elif hit.verb=='edit':
                        editing_index=hit.index;draft=CharacterDraft(party[hit.index])
                    elif hit.verb=='new' and len(party)<2:
                        class_id=tuple(CharacterClass)[hit.index]
                        key=next(key for key,build in PREMADE_CHARACTER_BUILDS.items() if build.class_levels[0].class_id is class_id)
                        editing_index=None;draft=new_draft(key)
                    elif hit.verb=='cancel':
                        draft=None;editing_index=None
                    elif hit.verb=='save' and draft is not None:
                        error=draft_error(draft.build)
                        if error:
                            draft=replace(draft,status=error)
                        else:
                            values=list(party)
                            if editing_index is None:
                                values.append(draft.build)
                            else:
                                values[editing_index]=draft.build
                            party=tuple(values);draft=None;editing_index=None
                    elif draft is not None:
                        draft=edit_draft(draft,hit,media,data)
            geometry=layout(screen.size);font=fonts(geometry.scale)
            hits,maximum=draw_creator(screen,geometry,font,skin,media,data,images,party,draft,status,pygame.mouse.get_pos())
            if draft is not None and draft.scroll>maximum:
                draft=replace(draft,scroll=maximum)
            if draft is not None and draft.page=='Appearance' and draft.choice is None:
                preview=pygame.Rect(geometry.modal.right-round(140*geometry.scale),geometry.modal.top+round(210*geometry.scale),
                                    round(140*geometry.scale),round(180*geometry.scale))
                draw_appearance(screen,draft.build,data,bodies,preview,pygame.time.get_ticks())
                text(screen,font.small,'Appearance only',preview.bottomleft,MUTED)
            pygame.display.flip()
            if capture_dir is not None and frame%6==0:
                pygame.image.save(screen,capture_dir/f'frame-{frame:05}.png')
            frame+=1;clock.tick(60)
        return None
    finally:
        pygame.quit()
