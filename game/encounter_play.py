"""Playable encounter: independent engine intake and one historical head.

The session owns commands. Retained lineages own subjective facts. Imported
contexts own presentation time. This frame pump connects those existing owners;
the renderer receives neither live entities nor an engine clock.
"""

import asyncio
from game.presentation_retained import RetainedPresentation, retain_presentation
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence, Literal
from uuid import UUID

import pygame

from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview, AvailableWorldInteraction, TargetType
from dnd.content.characters.builds import CharacterBuild
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows
from game.animation_types import Facing8
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import BoundChoreography
from game.choreography_draw import ChoreographyMedia, load_choreography_media, load_motion_media
from game.feedback import FeedbackTrack, choreography_feedback, motion_feedback
from game.motion_media import MotionMediaCue, bind_motion_media, choreography_motion_media
from game.controls import (ActionSelection, EndTurn, MenuState, selection_target_pool,
    begin_targeting, targeting_values, append_target, append_position, undo_targeting, confirm_targeting)
from game.motion import MotionTimeline
from game.playback_frame import sample_playback_frame
from game.presentation import capture_interval, capture_lineage
from game.player_facts import AttackFact, MovementFact, PlayerLineage, PlayerState, PlayerHUDSnapshot, StepFact, CombatLogAppend
from game.player_projection import begin_projection, project_lineage
from game.player_reduction import reduce_initialization, reduce_lineage
from game.presentation_group import (PresentationGroup, presentation_groups,
    reduce_presentation_group, stage_presentation_group, bind_presentation_group)
from game.projection import Camera, ZOOM_LEVELS
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from game.session import (
    Operation, advance_controller, close_session, create_session, discover_player_actions,
    end_player_turn, execute_player_action,
    preview_player_selection, snapshot_player_hud,
    equip_player_item, unequip_player_item, toggle_player_handler,
)
from game.visual_position import VisualPosition
from game.body_history import retain_body_head
from game.interaction_frame import InteractionFrame, pick_world, draw_highlights
from game.interaction_types import WorldHit
from game.ui_composition import compose_ui_media
from game.ui.action_bar import ActionFamily, ActionFamilyKey, action_families, family_at, default_shortcuts, shortcut_indices, shortcut_page, cost_label, variant_label
from game.ui.layout import layout
from game.ui.primitives import fonts, text, GREEN, GOLD
from game.ui.skin import load_skin
from game.ui.hud import draw_hud, draw_tooltip
from game.ui.combat_log import (LogHistory, LogView, LogLayout, group_log_rows, append_log_rows, retain_logs,
    draw_combat_log, copy_log_selection, scroll_log, log_text_position, drag_log_scroll)
from dnd.core.combat_log import CombatLogEntryType
from game.ui.targeting import draw_selection_preview, draw_movement_preview, undisclosed_position_at
from game.ui.types import UIFocus, UIFrame, UIHit, PendingInteraction, EquipItem, UnequipItem, ToggleHandler
from game.ui.world_interaction import world_options, admitted_world_actions, approach_action, main_attack, move_to, target_at


@dataclass(frozen=True, slots=True)
class GameFrame:
    index: int
    latest_cursor: int
    historical_cursor: int
    pending: int
    root_uuid: UUID | None
    elapsed_ms: float
    paused: bool
    input_ready: bool
    positions: tuple[tuple[str, tuple[float, float]], ...]
    hit_points: tuple[tuple[str, int | None], ...]


@dataclass(frozen=True, slots=True)
class GameSummary:
    latest: PlayerState
    historical: PlayerState
    frames: tuple[GameFrame, ...]
    lineages: tuple[PlayerLineage, ...]
    player_commands: int
    presentation_gaps: tuple[tuple[UUID, str], ...]
    encounter_ended: bool
    restart_requested: bool = False


PlayerInput = Callable[[PlayerState, AvailableActionsResult], ActionSelection | EndTurn | None]


async def _run(
    *, frame_deltas: Sequence[float] | None, frame_events: Mapping[int, Sequence[pygame.event.Event]],
    max_frames: int | None, window_size: tuple[int, int], quadrant: int,
    capture_dir: Path | None, capture_every: int, player_input: PlayerInput | None, stop_after_commands: int | None,
    exit_when_ended: bool, collect_frames: bool, encounter_id: str | None,
    player_positions: tuple[tuple[int, int], tuple[int, int]],
    enemy_positions: tuple[tuple[int, int], tuple[int, int]],
    player_builds: tuple[CharacterBuild, ...] | None, fullscreen: bool,
) -> GameSummary:
    pygame.init()
    windowed_size=window_size
    screen = pygame.display.set_mode((0,0) if fullscreen else window_size,
        pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
    window_size=screen.get_size()
    session = create_session(encounter_id=encounter_id,
        player_positions=player_positions, enemy_positions=enemy_positions,player_builds=player_builds)
    pygame.display.set_caption(f"D&D Engine — {session.encounter.name}")
    try:
        observer = session.game.entities[session.player_uuids[0]]
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="encounter startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=session.battlefield.definition.battlefield_id,
        )
        projection, initialization = begin_projection(startup)
        baseline = reduce_initialization(replace(initialization,hud_snapshot=snapshot_player_hud(session)))
        latest = historical = baseline
        catalog = load_catalog()
        data = load_animation_data(rig_files=tuple(sorted((Path(__file__).parent / "data/rigs").glob("*.json"))), world_source=catalog.world_source)
        number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx),
                                                       bold=style.fontWeight == "bold")
                                   for style in (data.number_style, data.badge_style))
        facings: dict[str, Facing8] = {}
        positions: dict[str, VisualPosition] = {}
        actors = scene_actors(historical, data, facings)
        body_media: LoadedBodyRows = {}
        load_scene_media(actors, data, body_rows=body_media)
        cache = SurfaceCache(catalog)
        media=compose_ui_media()
        skin=load_skin(media.resources)
        geometry=layout(window_size)
        ui_fonts=fonts(geometry.scale)
        ui_images: dict[tuple[str,tuple[int,int]],pygame.Surface]={}
        focus_ui: UIFocus=UIFocus(selected_actor=observer.uuid)
        rendered_focus: UIFocus=focus_ui
        pointer_focus: UIFocus=focus_ui
        ui_frame: UIFrame=UIFrame()
        interaction: InteractionFrame=InteractionFrame()
        pointer_capture: UIHit | None = None
        log_thumb_offset=0
        tooltip_lines: tuple[str,...]=()
        tooltip_point=(0,0)
        hover_since=ui_elapsed_ms=0.
        hud=baseline.hud_snapshot
        hud_pending: list[PlayerHUDSnapshot]=[]
        log_history: LogHistory=LogHistory()
        log_view: LogView=LogView()
        log_layout: LogLayout=LogLayout()
        log_hits_valid=False
        log_pending: list[tuple[tuple[CombatLogAppend, ...], UUID | None]]=[]
        feedback_viewport=geometry.viewport
        min_x, min_y, max_x, max_y = historical.world.bounds
        focus = ((min_x + max_x) / 2, (min_y + max_y) / 2)
        camera = Camera(quadrant=quadrant, zoom=1.0, viewport=window_size).with_focus(focus)
        camera = camera.with_screen_pan((0, -60*geometry.scale))
        pending: deque[PresentationGroup] = deque()
        retained: list[PlayerLineage] = []
        frames: list[GameFrame] = []
        gaps: list[tuple[UUID, str]] = []
        active: PlayerLineage | None = None
        active_group: PresentationGroup | None = None
        after = historical
        choreography: BoundChoreography | None = None
        motion: MotionTimeline | None = None
        choreography_media: ChoreographyMedia | None = None
        reaction_media: dict[UUID, ChoreographyMedia] = {}
        feedback: list[FeedbackTrack] = []
        motion_media: list[MotionMediaCue] = []
        choices: AvailableActionsResult | None = None
        view_choices: AvailableActionsResult | None = None
        families: tuple[ActionFamily,...]=()
        family_order: tuple[ActionFamilyKey,...]=()
        shortcuts: dict[UUID,tuple[ActionFamilyKey,...]]={}
        force_attack=False
        choice_force_attack=False
        menu: MenuState = MenuState()
        preview: AvailableSelectionPreview | None = None
        waiting_for_player = encounter_ended = paused = show_debug = False
        show_grid = False
        running = True
        restart_requested = False
        frame = issued = 0
        elapsed_ms = presentation_ms = 0.0
        presentation_lifetimes = retain_presentation(RetainedPresentation(), historical, data, absolute_start_ms=0, facings=facings)
        body_history = retain_body_head((), historical, None, start_ms=0, facings=facings, positions=positions)
        clock = pygame.time.Clock()
        if capture_dir is not None:
            capture_dir.mkdir(parents=True, exist_ok=True)

        def receive(operation: Operation) -> None:
            nonlocal latest
            if operation.hud_snapshot is not None:
                hud_pending.append(operation.hud_snapshot)
            received = []
            for root in operation.roots:
                native = capture_lineage(root, observer_uuid=observer.uuid,
                                         known_actor_uuids=frozenset(latest.actors))
                lineage = project_lineage(projection, native)
                if lineage is None:
                    continue
                latest = reduce_lineage(latest, lineage)
                received.append(lineage)
                retained.append(lineage)
                classes = {row.event_uuid: row.event_class for row in native.objective_rows}
                gaps.extend((identity, f"Unprojected state payload: {classes[identity]}")
                            for identity, _ in native.dispositions)
            groups = presentation_groups(tuple(received))
            pending.extend(groups)
            if operation.combat_log_appends:
                # The last received group is this operation's visual boundary.
                # A later operation must not postpone its standalone entries.
                log_pending.append((operation.combat_log_appends,
                    groups[-1].primary.root.uuid if groups else
                    pending[-1].primary.root.uuid if pending else
                    active_group.primary.root.uuid if active_group is not None else None))

        def refresh_preview() -> None:
            nonlocal preview
            preview=None
            if menu.active and choices is not None and historical.current_actor_uuid is not None:
                row=choices.all_actions[menu.selected_action]
                preview=preview_player_selection(session,historical.current_actor_uuid,row,
                    targeting_values(menu,row),menu.selected_positions)

        def select_row(index: int) -> ActionSelection | None:
            nonlocal menu,focus_ui
            assert choices is not None
            row=choices.all_actions[index]
            focus_ui=replace(focus_ui,family=None,variant_index=None,context=(),panel=None,pending=None,pinned_tooltip=())
            menu=begin_targeting(index)
            refresh_preview()
            if row.target_type is TargetType.SELF and preview is not None and preview.next_targets:
                menu=append_target(menu,preview,preview.next_targets[0].index)
                refresh_preview()
                return confirm_targeting(menu,preview) if preview is not None else None
            return None

        def select_world(option: AvailableWorldInteraction) -> ActionSelection | None:
            nonlocal menu,focus_ui
            assert choices is not None and historical.current_actor_uuid is not None
            direct=admitted_world_actions(choices,option)
            focus_ui=replace(focus_ui,context=(),family=None)
            if len(direct)==1:
                return direct[0]
            if len(direct)>1:
                # Connector sides/destinations stay exact native target choices.
                return select_row(direct[0].action_index)
            approach=approach_action(choices,option)
            if approach is not None:
                focus_ui=replace(focus_ui,pending=PendingInteraction(historical.current_actor_uuid,
                    option.subject_uuid,option,choices.discovery_generation))
                return approach[0]
            menu=replace(menu,status=option.reason or 'No admitted safe approach')
            return None

        def resize_display(size: tuple[int,int], toggle: bool = False) -> None:
            nonlocal screen,geometry,ui_fonts,camera,feedback_viewport,fullscreen,windowed_size,ui_frame,pointer_capture
            pointer_capture=None
            if toggle:
                if not fullscreen:
                    windowed_size=screen.get_size()
                fullscreen=not fullscreen
                screen=pygame.display.set_mode((0,0) if fullscreen else windowed_size,
                    pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
            else:
                current=pygame.display.get_surface()
                assert current is not None
                screen=(pygame.display.set_mode(size,pygame.RESIZABLE)
                    if not fullscreen and size!=current.get_size() else current)
            old=camera.viewport
            actual=screen.get_size()
            camera=replace(camera,viewport=actual,pan=(camera.pan[0]+(actual[0]-old[0])/2,camera.pan[1]+(actual[1]-old[1])/2))
            geometry=layout(actual,focus_ui.ui_scale)
            ui_fonts=fonts(geometry.scale)
            feedback_viewport=geometry.viewport
            ui_frame=UIFrame(blocked=(geometry.viewport,))

        def apply_ui_hit(hit: UIHit, *, ready: bool, clicks: int,
                         command: ActionSelection | EndTurn | EquipItem | UnequipItem | ToggleHandler | None,
                         ) -> ActionSelection | EndTurn | EquipItem | UnequipItem | ToggleHandler | None:
            """Dispatch an admitted painted control within the existing frame owner."""
            nonlocal focus_ui, log_view, log_hits_valid, running, restart_requested
            nonlocal menu, preview, choices, camera
            verb=hit.verb
            match verb:
                case 'close':
                    focus_ui=replace(focus_ui,panel=None,family=None,context=())
                case 'quit':
                    running=False
                case 'retry':
                    restart_requested=True;running=False
                case 'fullscreen':
                    resize_display(screen.get_size(),toggle=True)
                case 'scale':
                    focus_ui=replace(focus_ui,ui_scale={1.:1.25,1.25:1.5,1.5:1.}[focus_ui.ui_scale])
                    resize_display(screen.get_size())
                case 'log':
                    focus_ui=replace(focus_ui,log_open=not focus_ui.log_open)
                case 'log_row' if hit.log_key is not None:
                    log_view=replace(log_view,selected=hit.log_key,selection_anchor=None)
                case 'log_expand' if hit.log_key is not None:
                    collapsed=set(log_view.collapsed)
                    if hit.log_key in collapsed:
                        collapsed.remove(hit.log_key)
                    else:
                        collapsed.add(hit.log_key)
                    log_view=replace(log_view,selected=hit.log_key,collapsed=frozenset(collapsed),selection_anchor=None)
                    log_hits_valid=False
                case 'log_detail':
                    log_view=replace(log_view,detailed=not log_view.detailed,selection_anchor=None)
                    log_hits_valid=False
                case 'log_follow':
                    log_view=replace(log_view,follow=True)
                    log_hits_valid=False
                case 'log_filter':
                    categories=(None,*tuple(CombatLogEntryType))
                    log_view=replace(log_view,category=categories[(categories.index(log_view.category)+1)%len(categories)],selection_anchor=None)
                    log_hits_valid=False
                case 'log_actor':
                    log_view=replace(log_view,actor_uuid=focus_ui.selected_actor if log_view.actor_uuid is None else None,selection_anchor=None)
                    log_hits_valid=False
                case 'log_copy':
                    copied=copy_log_selection(log_history,log_view)
                    if copied:
                        pygame.scrap.put_text(copied)
                case 'page':
                    pins=shortcuts.get(view_choices.entity_uuid,()) if view_choices is not None else ()
                    focus_ui=replace(focus_ui,bar_page=shortcut_page(focus_ui.bar_page+hit.index,len(pins),geometry.columns))
                case 'inspect' if hit.identity is not None:
                    focus_ui=replace(focus_ui,selected_actor=hit.identity)
                    if clicks>1 and hit.identity in historical.actors:
                        contact=next((actor.contact for actor in actors if actor.contact.actor_uuid==str(hit.identity)),None)
                        if contact is not None:
                            camera=camera.with_focus(contact.grid)
                case 'attack_mode':
                    focus_ui=replace(focus_ui,attack_preference='RANGED_MAIN' if focus_ui.attack_preference=='MELEE_MAIN' else 'MELEE_MAIN')
                case 'panel':
                    focus_ui=replace(focus_ui,panel=('inventory','sheet','spellbook','reactions')[hit.index],family=None,context=(),pending=None,popup_scroll=0)
                    menu=MenuState();preview=None
                case 'inventory_item':
                    focus_ui=replace(focus_ui,selected_item=hit.identity,item_detail_scroll=0)
                case 'library_filter':
                    filters: tuple[Literal['all','spells','actions','items'],...] = ('all','spells','actions','items')
                    focus_ui=replace(focus_ui,library_filter=filters[hit.index],popup_scroll=0)
                case 'pin' if choices is not None and hit.family_key is not None:
                    pins=shortcuts.get(choices.entity_uuid,())
                    shortcuts[choices.entity_uuid]=(tuple(key for key in pins if key!=hit.family_key) if hit.family_key in pins else (*pins,hit.family_key))
                case _ if ready and choices is not None and command is None:
                    if hit.verb=='end' and not menu.active and focus_ui.family is None and not focus_ui.context and focus_ui.panel is None:
                        command=EndTurn()
                    elif hit.verb=='cancel':
                        menu=MenuState();preview=None
                        if choice_force_attack!=force_attack:
                            choices=None
                    elif hit.verb=='confirm':
                        refresh_preview()
                        command=confirm_targeting(menu,preview) if preview is not None else None
                    elif hit.verb=='family':
                        family=family_at(families,hit.index)
                        if family is None:
                            return command
                        if len(family.indices)>1:
                            focus_ui=replace(focus_ui,family=hit.index,variant_index=None,popup_scroll=0,context=(),panel=None,pending=None)
                            menu=MenuState();preview=None
                        elif len(family.indices)==1:
                            command=select_row(family.indices[0])
                    elif hit.verb=='variant':
                        command=select_row(hit.index)
                    elif hit.verb=='variant_pick':
                        focus_ui=replace(focus_ui,variant_index=hit.index)
                    elif hit.verb=='world' and hit.index<len(focus_ui.context):
                        command=select_world(focus_ui.context[hit.index])
                    elif hit.verb=='equip' and hit.identity is not None and hit.equipment_slot is not None:
                        command=EquipItem(hit.identity,hit.equipment_slot)
                    elif hit.verb=='unequip' and hit.equipment_slot is not None:
                        command=UnequipItem(hit.equipment_slot)
                    elif hit.verb=='handler' and hit.identity is not None:
                        handler=next((row for row in choices.handler_details if row.uuid==hit.identity),None)
                        if handler is not None:
                            command=ToggleHandler(handler.uuid,not handler.enabled)
            return command

        while running and (max_frames is None or frame < max_frames):
            delta = (clock.tick(60) / 1000 if frame_deltas is None
                     else frame_deltas[min(frame, len(frame_deltas) - 1)])
            if not paused:
                presentation_ms += delta * 1000
            ui_elapsed_ms += delta*1000
            ready = waiting_for_player and active is None and not pending and not paused and geometry.supported
            if ready and choices is not None and not menu.active and choice_force_attack!=force_attack:
                choices=None
            if ready and choices is None:
                actor_uuid = historical.current_actor_uuid
                if actor_uuid is None:
                    raise RuntimeError("human boundary lacks its displayed turn owner")
                choices = discover_player_actions(session,actor_uuid,force_attack=force_attack)
                choice_force_attack=force_attack
                if view_choices is None or focus_ui.selected_actor==view_choices.entity_uuid:
                    focus_ui=replace(focus_ui,selected_actor=actor_uuid)
                view_choices=choices
                families=action_families(choices,family_order)
                family_order=tuple(family.key for family in families)
                shortcuts.setdefault(actor_uuid,default_shortcuts(choices,families))
                menu=MenuState(status=menu.status)
                preview=None
            command: ActionSelection | EndTurn | EquipItem | UnequipItem | ToggleHandler | None = None
            for event in frame_events.get(frame, ()):
                pygame.event.post(event)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running=False
                    continue
                if event.type == pygame.WINDOWRESIZED:
                    resize_display((event.x,event.y))
                    continue
                if event.type == pygame.KEYUP and event.key in (pygame.K_LCTRL,pygame.K_RCTRL):
                    was_forced=force_attack
                    force_attack=False
                    if was_forced and ready and not menu.active and command is None:
                        assert historical.current_actor_uuid is not None
                        choices=discover_player_actions(session,historical.current_actor_uuid,force_attack=False)
                        choice_force_attack=False
                        view_choices=choices;families=action_families(choices,family_order)
                        focus_ui=replace(focus_ui,context=(),family=None)
                    continue
                if event.type == pygame.KEYDOWN:
                    pointer_capture=None
                    modifiers=event.dict.get('mod',pygame.key.get_mods())
                    if event.key==pygame.K_RETURN and modifiers&pygame.KMOD_ALT:
                        resize_display(screen.get_size(),toggle=True)
                        continue
                    if event.key==pygame.K_c and modifiers&pygame.KMOD_CTRL and focus_ui.log_open and log_view.selected is not None:
                        copied=copy_log_selection(log_history,log_view)
                        if copied:
                            pygame.scrap.put_text(copied)
                        continue
                    if event.key in (pygame.K_LCTRL,pygame.K_RCTRL) and focus_ui.log_open and (log_view.selected is not None or geometry.log.collidepoint(pygame.mouse.get_pos())):
                        continue
                    if event.key==pygame.K_ESCAPE:
                        if focus_ui.family is not None or focus_ui.context:
                            focus_ui=replace(focus_ui,family=None,context=())
                        elif menu.active or focus_ui.pending is not None:
                            menu=MenuState();preview=None
                            focus_ui=replace(focus_ui,pending=None)
                        elif focus_ui.panel is not None or focus_ui.pinned_tooltip:
                            focus_ui=replace(focus_ui,panel=None,pinned_tooltip=())
                        else:
                            focus_ui=replace(focus_ui,panel='menu')
                        if not menu.active and choice_force_attack!=force_attack:
                            choices=None
                        continue
                    if event.key==pygame.K_PAUSE:
                        paused=not paused
                        if paused:
                            ready=False
                            command=None
                        continue
                    if focus_ui.panel=='spellbook':
                        if event.key==pygame.K_BACKSPACE:
                            focus_ui=replace(focus_ui,search_text=focus_ui.search_text[:-1],popup_scroll=0)
                        continue
                    if event.key==pygame.K_F12:
                        show_debug=not show_debug
                        continue
                    if event.key==pygame.K_g:
                        show_grid=not show_grid
                        continue
                    if event.key in (pygame.K_q,pygame.K_e):
                        camera=camera.quarter_turned(-1 if event.key==pygame.K_q else 1)
                        continue
                    if event.key==pygame.K_t:
                        focus_ui=replace(focus_ui,pinned_tooltip=tooltip_lines,tooltip_position=tooltip_point)
                        continue
                    if event.key==pygame.K_r and encounter_ended and active is None and not pending:
                        restart_requested=True;running=False
                        continue
                    panels: dict[int,Literal['inventory','sheet','spellbook','reactions']]={pygame.K_i:'inventory',pygame.K_n:'sheet',pygame.K_k:'spellbook',pygame.K_l:'reactions'}
                    if event.key in panels:
                        panel_name=panels[event.key]
                        focus_ui=replace(focus_ui,panel=None if focus_ui.panel==panel_name else panel_name,family=None,context=(),pending=None,popup_scroll=0)
                        menu=MenuState();preview=None
                        continue
                    if focus_ui.panel is not None:
                        continue
                    if event.key in (pygame.K_F1,pygame.K_F2,pygame.K_F3,pygame.K_F4):
                        offset=event.key-pygame.K_F1
                        if offset<len(session.player_uuids):
                            focus_ui=replace(focus_ui,selected_actor=session.player_uuids[offset])
                        continue
                    if ready and command is None and choices is not None:
                        if event.key in (pygame.K_LCTRL,pygame.K_RCTRL) and not menu.active:
                            force_attack=True
                            assert historical.current_actor_uuid is not None
                            choices=discover_player_actions(session,historical.current_actor_uuid,force_attack=True)
                            choice_force_attack=True
                            view_choices=choices;families=action_families(choices,family_order)
                            focus_ui=replace(focus_ui,context=(),family=None)
                        elif event.key==pygame.K_SPACE and not menu.active and focus_ui.family is None and not focus_ui.context and focus_ui.pending is None:
                            command=EndTurn()
                        elif event.key==pygame.K_RETURN and menu.active:
                            refresh_preview()
                            command=confirm_targeting(menu,preview) if preview is not None else None
                        elif event.key==pygame.K_BACKSPACE and menu.active:
                            menu=undo_targeting(menu);refresh_preview()
                        else:
                            hotkeys=(pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4,pygame.K_5,pygame.K_6,
                                pygame.K_7,pygame.K_8,pygame.K_9,pygame.K_0,pygame.K_MINUS,pygame.K_EQUALS)
                            if event.key in hotkeys:
                                offset=hotkeys.index(event.key)
                                pins=shortcut_indices(families,shortcuts.get(choices.entity_uuid,()))
                                page=shortcut_page(focus_ui.bar_page,len(pins),geometry.columns)
                                slot=page*geometry.columns+offset
                                index=pins[slot] if slot<len(pins) else None
                                family=family_at(families,index) if index is not None else None
                                if offset<geometry.columns and family is not None:
                                    if len(family.indices)>1:
                                        focus_ui=replace(focus_ui,family=index,variant_index=None,popup_scroll=0,context=(),pending=None)
                                        menu=MenuState();preview=None
                                    elif len(family.indices)==1:
                                        command=select_row(family.indices[0])
                    continue
                if event.type==pygame.TEXTINPUT and focus_ui.panel=='spellbook':
                    focus_ui=replace(focus_ui,search_text=(focus_ui.search_text+event.text)[:80],popup_scroll=0)
                    continue
                if event.type==pygame.MOUSEWHEEL:
                    point=pygame.mouse.get_pos()
                    if focus_ui.log_open and focus_ui.panel is None and geometry.log.collidepoint(point):
                        log_view=scroll_log(log_view,log_layout,-event.y*ui_fonts.small.get_linesize()*3)
                        log_hits_valid=False
                        pointer_capture=None
                    elif focus_ui.panel=='inventory' and ui_frame.detail_scroll_rect is not None and ui_frame.detail_scroll_rect.collidepoint(point):
                        focus_ui=replace(focus_ui,item_detail_scroll=max(0,focus_ui.item_detail_scroll-event.y*ui_fonts.small.get_linesize()*3))
                    elif focus_ui.family is not None or focus_ui.context or focus_ui.panel is not None:
                        focus_ui=replace(focus_ui,popup_scroll=max(0,focus_ui.popup_scroll-event.y))
                    elif geometry.bar.collidepoint(point):
                        pins=shortcuts.get(view_choices.entity_uuid,()) if view_choices is not None else ()
                        focus_ui=replace(focus_ui,bar_page=shortcut_page(focus_ui.bar_page-event.y,len(pins),geometry.columns))
                    elif not any(rect.collidepoint(point) for rect in ui_frame.blocked):
                        zoom_index=max(0,min(len(ZOOM_LEVELS)-1,ZOOM_LEVELS.index(camera.zoom)+event.y))
                        camera=camera.with_zoom_at(ZOOM_LEVELS[zoom_index],point)
                    continue
                if event.type==pygame.MOUSEMOTION and pointer_capture is not None and focus_ui==pointer_focus:
                    if pointer_capture.verb=='log_text' and log_hits_valid and log_view.selection_anchor is not None:
                        selected=log_text_position(log_layout,event.pos,log_view.selection_anchor[0])
                        if selected is not None:
                            log_view=replace(log_view,selection_end=selected[1])
                    elif pointer_capture.verb=='log_scrollbar':
                        log_view=drag_log_scroll(log_view,log_layout,event.pos[1],log_thumb_offset)
                        log_hits_valid=False
                    continue
                if event.type not in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
                    continue
                point=event.pos
                if event.type==pygame.MOUSEBUTTONDOWN and event.button==3:
                    pointer_capture=None
                    if menu.active or focus_ui.pending is not None:
                        menu=MenuState();preview=None
                        focus_ui=replace(focus_ui,pending=None)
                        if choice_force_attack!=force_attack:
                            choices=None
                        continue
                    shortcut=next((world_hit for world_hit in reversed(ui_frame.hits)
                        if world_hit.rect.collidepoint(point) and world_hit.family_key is not None and geometry.bar.colliderect(world_hit.rect)),None)
                    if shortcut is not None and view_choices is not None and focus_ui.panel is None:
                        pins=shortcuts.get(view_choices.entity_uuid,())
                        shortcuts[view_choices.entity_uuid]=tuple(key for key in pins if key!=shortcut.family_key)
                        continue
                    if any(rect.collidepoint(point) for rect in ui_frame.blocked):
                        continue
                    if focus_ui.family is not None or focus_ui.context:
                        focus_ui=replace(focus_ui,family=None,context=())
                    elif ready and choices is not None and focus_ui.panel is None:
                        world_hit=pick_world(interaction,point)
                        if world_hit is not None:
                            focus_ui=replace(focus_ui,context=world_options(choices,world_hit),context_position=point)
                    continue
                if event.button!=1:
                    continue
                if event.type==pygame.MOUSEBUTTONDOWN:
                    if focus_ui!=rendered_focus:
                        pointer_capture=None
                        continue
                    pointer_focus=focus_ui
                    pointer_capture=next((world_hit for world_hit in reversed(ui_frame.hits) if world_hit.rect.collidepoint(point)),None)
                    label_hit=pointer_capture.world_hit if pointer_capture is not None else None
                    if label_hit is not None:
                        pointer_capture=None
                    elif pointer_capture is not None:
                        if pointer_capture.verb.startswith('log_') and not log_hits_valid:
                            pointer_capture=None
                            continue
                        if pointer_capture.verb=='log_text':
                            selected=log_text_position(log_layout,point)
                            if selected is not None:
                                log_view=replace(log_view,selected=selected[0],selection_anchor=selected,selection_end=selected[1],follow=False)
                        elif pointer_capture.verb=='log_scrollbar':
                            thumb=log_layout.scrollbar_thumb
                            log_thumb_offset=point[1]-thumb.top if thumb is not None and thumb.collidepoint(point) else (thumb.height//2 if thumb else 0)
                            log_view=drag_log_scroll(log_view,log_layout,point[1],log_thumb_offset)
                            log_hits_valid=False
                        continue
                    elif any(rect.collidepoint(point) for rect in ui_frame.blocked):
                        continue
                    if focus_ui.family is not None or focus_ui.context:
                        focus_ui=replace(focus_ui,family=None,context=())
                        continue
                    if not ready or choices is None or command is not None or focus_ui.panel is not None:
                        continue
                    world_hit=label_hit or pick_world(interaction,point)
                    if menu.active:
                        row=choices.all_actions[menu.selected_action]
                        refresh_preview()
                        if preview is None:
                            continue
                        if menu.selected_targets and preview.next_positions:
                            position=((round(world_hit.position[0]),round(world_hit.position[1])) if world_hit is not None
                                else undisclosed_position_at(point,preview,
                                    {p:t for p,t in historical.tiles.items() if historical.senses is not None and p in historical.senses.visible},camera))
                            if position is not None:
                                menu=append_position(menu,preview,position);refresh_preview()
                            continue
                        target=target_at(preview.next_targets,world_hit) if world_hit is not None else None
                        if target is not None:
                            menu=append_target(menu,preview,target.index);refresh_preview()
                            explicit=(row.target_type is TargetType.MULTI_ENTITY or row.position_selection is not None
                                and row.position_selection.kind in ('path','entity_destination'))
                            if not explicit and preview is not None:
                                command=confirm_targeting(menu,preview)
                    elif world_hit is not None:
                        focus_ui=replace(focus_ui,pending=None)
                        if world_hit.kind=='ground':
                            if not force_attack:
                                command=move_to(choices,(round(world_hit.position[0]),round(world_hit.position[1])))
                        elif world_hit.kind=='actor':
                            command=main_attack(choices,UUID(world_hit.identity),focus_ui.attack_preference)
                            if command is None:
                                focus_ui=replace(focus_ui,selected_actor=UUID(world_hit.identity))
                        elif force_attack and world_hit.kind=='object':
                            command=main_attack(choices,UUID(world_hit.identity),focus_ui.attack_preference)
                        elif not force_attack:
                            options=world_options(choices,world_hit)
                            defaults=tuple(option for option in options if option.default_priority==options[0].default_priority) if options else ()
                            if len(defaults)==1:
                                command=select_world(defaults[0])
                            elif defaults:
                                focus_ui=replace(focus_ui,context=options,context_position=point)
                    continue
                hit=pointer_capture
                pointer_capture=None
                if hit is not None and hit.verb in ('log_text','log_scrollbar'):
                    continue
                if hit is None:
                    continue
                if focus_ui!=pointer_focus or not hit.rect.collidepoint(point) or not hit.enabled:
                    continue
                if hit.verb.startswith('log_') and not log_hits_valid:
                    continue
                if hit.discovery_generation is not None and (choices is None or hit.discovery_generation!=choices.discovery_generation):
                    continue
                command=apply_ui_hit(hit,ready=ready,clicks=event.dict.get('clicks',1),command=command)
            if (ready and command is None and focus_ui.pending is not None and choices is not None
                    and not menu.active and focus_ui.panel is None and focus_ui.family is None and not focus_ui.context):
                intent=focus_ui.pending
                option=next((option for option in choices.world_interactions
                    if option.subject_uuid==intent.subject_uuid and option.behavior_id==intent.descriptor.behavior_id
                    and option.template_name==intent.descriptor.template_name
                    and option.connector_uuid==intent.descriptor.connector_uuid and option.configured_action_ref==intent.descriptor.configured_action_ref
                    and option.variant_facets==intent.descriptor.variant_facets),None)
                if intent.move_generation<choices.discovery_generation:
                    focus_ui=replace(focus_ui,pending=None)
                    direct=admitted_world_actions(choices,option) if option is not None and intent.actor_uuid==historical.current_actor_uuid else ()
                    if len(direct)==1:
                        command=direct[0]
                    elif direct:
                        command=select_row(direct[0].action_index)
                    else:
                        menu=replace(menu,status='Interaction canceled: no longer admitted')
            if not running:
                break
            if ready and not paused and command is None and player_input is not None and choices is not None:
                if stop_after_commands is None or issued < stop_after_commands:
                    command = player_input(historical, choices)
            if ready and command is not None and choices is not None and not paused:
                actor_uuid = historical.current_actor_uuid
                assert actor_uuid is not None
                accepted: Operation | None=None
                try:
                    match command:
                        case EndTurn():
                            accepted = end_player_turn(session, actor_uuid)
                        case ActionSelection():
                            action = choices.all_actions[command.action_index]
                            selected = tuple(next(target for target in selection_target_pool(action, command.target_indices)
                                                  if target.index == index) for index in command.target_indices)
                            if not selected:
                                raise ValueError("player command requires its discovered target")
                            accepted = execute_player_action(
                                session, actor_uuid, action, selected[0],
                                extra_target_uuids=tuple(target.target_uuid for target in selected[1:]
                                                         if target.target_uuid is not None),
                                extra_target_positions=command.extra_target_positions,
                            )
                        case EquipItem():
                            accepted=equip_player_item(session,actor_uuid,command.item_uuid,command.slot)
                        case UnequipItem():
                            accepted=unequip_player_item(session,actor_uuid,command.slot)
                        case ToggleHandler():
                            accepted=toggle_player_handler(session,actor_uuid,command.handler_uuid,command.enabled)
                except ValueError as error:
                    menu=MenuState(status=str(error))
                    focus_ui=replace(focus_ui,pending=None)
                if accepted is not None:
                    receive(accepted)
                    menu=MenuState()
                    waiting_for_player = False
                    issued += 1
                choices = None
                preview=None
                focus_ui=replace(focus_ui,family=None,context=())

            # Independent process: a native decision can run while history is
            # paused or animating. No rendered duration enters the rules engine.
            if not waiting_for_player and not encounter_ended:
                operation = advance_controller(session)
                receive(operation)
                assert operation.boundary is not None
                if operation.boundary.status == "error":
                    raise RuntimeError("encounter has no valid controller action boundary")
                waiting_for_player = operation.boundary.status == "waiting_for_human"
                encounter_ended = operation.boundary.status == "encounter_ended"
            await asyncio.sleep(0)

            started = False
            if active is None and pending and not paused:
                active_group = pending.popleft()
                active = active_group.primary
                after = reduce_presentation_group(historical, active_group)
                load_scene_media((
                    *scene_actors(stage_presentation_group(historical, active_group), data, facings),
                    *scene_actors(after, data, facings),
                ), data, body_rows=body_media)
                choreography = None
                choreography_media = None
                contacts = {actor.contact.actor_uuid: actor.contact
                            for actor in scene_actors(historical, data, facings, positions)}
                activated_conditions = frozenset(owner for owner, lifetime in presentation_lifetimes.conditions.items()
                    if lifetime.activated_ms is not None and lifetime.activated_ms <= presentation_ms)
                bound = bind_presentation_group(historical, active_group, data, facings=facings,
                    contacts=contacts, activated_conditions=activated_conditions)
                motion = bound if isinstance(bound, MotionTimeline) else None
                reaction_media = {}
                if motion is not None:
                    reaction_media = load_motion_media(motion, data, body_rows=body_media)
                    for reaction in motion.reactions:
                        group = reaction.choreography
                        gaps.extend(group.gaps)
                    feedback.extend(motion_feedback(motion, data, presentation_ms))
                else:
                    if isinstance(active.root.fact, MovementFact) and any(
                        isinstance(event.fact, AttackFact) or (isinstance(event.fact, StepFact) and event.fact.committed)
                        for event in active.events
                    ):
                        gaps.append((active.root.uuid, "Movement reaction choreography is not bound"))
                    assert isinstance(bound, BoundChoreography)
                    choreography = bound
                    choreography_media = load_choreography_media(choreography, body_rows=body_media)
                    gaps.extend(choreography.gaps)
                    feedback.extend(choreography_feedback(choreography, data, presentation_ms, contacts=contacts))
                presentation_lifetimes = retain_presentation(presentation_lifetimes, historical, data, absolute_start_ms=presentation_ms,
                    lineage=active, choreography=choreography, motion=motion, facings=facings)
                if motion is not None:
                    motion_media.extend(bind_motion_media(motion, data, presentation_ms))
                elif choreography is not None:
                    motion_media.extend(choreography_motion_media(choreography, data, presentation_ms))
                body_history = retain_body_head(body_history, historical, after, start_ms=presentation_ms,
                    facings=facings, positions=positions, choreography=choreography, motion=motion)
                log_history=retain_logs(log_history,group_log_rows(active_group,choreography=choreography,motion=motion,start_ms=presentation_ms))
                elapsed_ms = 0
                started = True
                clock.tick()
            if active is not None and not started and not paused:
                elapsed_ms += delta * 1000
            keys = pygame.key.get_pressed()
            if focus_ui.panel is None:
                camera = camera.with_screen_pan(((keys[pygame.K_a] - keys[pygame.K_d]) * 320 * delta,
                                                 (keys[pygame.K_w] - keys[pygame.K_s]) * 320 * delta))
            feedback[:] = [track for track in feedback if presentation_ms < track.start_ms + track.duration_ms]
            motion_media[:] = [cue for cue in motion_media if presentation_ms < cue.media.end_ms]
            playback = sample_playback_frame(
                historical, after if active is not None else None, data, elapsed_ms, presentation_ms,
                camera, facings, body_media, number_font, badge_font,
                choreography=choreography, choreography_media=choreography_media,
                motion=motion, reaction_media=reaction_media, feedback=feedback, condition_lifetimes=presentation_lifetimes.conditions,
                spatial_lifetimes=presentation_lifetimes.spatial, item_starts=presentation_lifetimes.items, construction_lifetimes=presentation_lifetimes.construction, concentration_lifetimes=presentation_lifetimes.concentration, deposit_starts=presentation_lifetimes.deposits,
                positions=positions, feedback_viewport=feedback_viewport, motion_media=motion_media, body_history=body_history,
            )
            displayed, actors, commands = playback.displayed, playback.actors, playback.commands
            complete, shown_hp = playback.complete, playback.shown_hp
            facings = dict(playback.facings)
            positions = dict(playback.positions)
            scene=draw_frame(screen, displayed, catalog, cache, camera, presentation_ms / 1000,
                show_grid=show_grid, show_debug=show_debug, mouse_position=None,collect_interaction=True,
                objective_lines=tuple(f"[{identity}] {reason}" for identity, reason in gaps[-8:]),
                extra_commands=commands, animation_data=data, item_starts=presentation_lifetimes.items,
                world_transitions=playback.world_transitions, residue_reveals=playback.residue_reveals,
                deposited_materials=playback.deposited_materials,
                revisions=(latest.reducer_cursor, latest.reducer_cursor, historical.reducer_cursor))
            interaction=scene.interaction or InteractionFrame()
            ready=waiting_for_player and active is None and not pending and not paused and geometry.supported
            if active is None and not pending and hud_pending:
                hud=hud_pending[-1]
                hud_pending.clear()
            immediate = tuple(row for rows, owner in log_pending if owner is None for row in rows)
            if immediate:
                log_history=retain_logs(log_history,append_log_rows(immediate,reveal_ms=presentation_ms))
                log_pending[:] = [(rows, owner) for rows, owner in log_pending if owner is not None]
            mouse=pygame.mouse.get_pos()
            hover=None if any(rect.collidepoint(mouse) for rect in ui_frame.blocked) else pick_world(interaction,mouse)
            highlights: list[tuple[WorldHit,tuple[int,int,int]]]=[]
            world_labels: list[UIHit]=[]
            hovered_target=None
            visible_tiles={position:tile for position,tile in displayed.tiles.items()
                if displayed.senses is not None and position in displayed.senses.visible}
            if ready and menu.active and choices is not None:
                refresh_preview()
                if preview is not None:
                    eligible={str(target.target_uuid) for target in preview.next_targets if target.target_uuid is not None}
                    selected={str(target.target_uuid) for target in targeting_values(menu,choices.all_actions[menu.selected_action]) if target.target_uuid is not None}
                    highlights.extend((region.hit,GOLD if region.hit.identity in selected else GREEN)
                        for region in interaction.regions if region.hit.identity in eligible|selected)
                    hovered_target=target_at(preview.next_targets,hover) if hover is not None else None
                    values=targeting_values(menu,choices.all_actions[menu.selected_action])
                    points=tuple(target.position for target in values if target.position is not None)+menu.selected_positions
                    draw_selection_preview(screen,preview,visible_tiles,camera,hovered_target,
                        selected=values,points=points if choices.all_actions[menu.selected_action].position_selection is not None else (),font=ui_fonts.small)
                    if hovered_target is not None and choices.all_actions[menu.selected_action].behavior_id=='action.move':
                        draw_movement_preview(screen,hovered_target,choices.remaining_movement,visible_tiles,camera,ui_fonts.small)
            elif ready and choices is not None and hover is not None and focus_ui.panel is None and focus_ui.family is None and not focus_ui.context and not force_attack:
                movement = None
                if hover.kind=='ground':
                    selected_move=move_to(choices,(round(hover.position[0]),round(hover.position[1])))
                    if selected_move is not None:
                        movement=next(target for target in choices.all_actions[selected_move.action_index].valid_targets
                            if target.index==selected_move.target_indices[0])
                else:
                    options=world_options(choices,hover)
                    if options and not admitted_world_actions(choices,options[0]):
                        approach=approach_action(choices,options[0])
                        movement=approach[1] if approach is not None else None
                if movement is not None:
                    draw_movement_preview(screen,movement,choices.remaining_movement,visible_tiles,camera,ui_fonts.small)
            if hover is not None:
                highlights.append((hover,GOLD))
            if pygame.key.get_mods()&pygame.KMOD_ALT and choices is not None:
                subjects={str(option.subject_uuid) for option in choices.world_interactions}
                seen=set()
                for region in interaction.regions:
                    if region.hit.identity not in subjects or region.hit.identity in seen:
                        continue
                    seen.add(region.hit.identity)
                    highlights.insert(0,(region.hit,GREEN))
                    obj=displayed.objects.get(UUID(region.hit.identity))
                    if obj is not None:
                        label=text(screen,ui_fonts.small,obj.item.name,(region.destination[0],region.destination[1]-ui_fonts.small.get_height()),GREEN)
                        options=world_options(choices,region.hit)
                        if options:
                            world_labels.append(UIHit(label,'world',label=obj.item.name,world_hit=region.hit,
                                discovery_generation=choices.discovery_generation))
            draw_highlights(screen,interaction,highlights)
            settled_end=encounter_ended and active is None and not pending
            outcome='You survived' if historical.actors[observer.uuid].life_state is LifeState.ALIVE else 'You fell'
            status=f'Encounter complete · {outcome}' if settled_end else 'Paused' if paused else 'Your turn' if ready else 'Playing history'
            if menu.status and not menu.active:
                status=menu.status
            if not geometry.supported:
                status='Resize to at least 960 × 540'
            ui_frame=draw_hud(screen,geometry,ui_fonts,skin,media,ui_images,displayed,hud,view_choices,
                families,menu,focus_ui,preview,ready=ready,mouse=mouse,status=status,shown_hp=shown_hp,shortcuts=shortcuts.get(view_choices.entity_uuid,()) if view_choices is not None else ())
            if ui_frame.detail_scroll_max is not None:
                focus_ui=replace(focus_ui,item_detail_scroll=min(focus_ui.item_detail_scroll,ui_frame.detail_scroll_max))
            rendered_focus=focus_ui
            if focus_ui.panel is None:
                ui_frame=UIFrame((*tuple(world_labels),*ui_frame.hits),(*tuple(hit.rect for hit in world_labels),*ui_frame.blocked))
            if focus_ui.log_open and focus_ui.panel is None:
                log_frame,log_view=draw_combat_log(screen,geometry,ui_fonts,skin,log_history,log_view,log_layout,displayed,
                    now_ms=presentation_ms,mouse=mouse)
                ui_frame=UIFrame((*ui_frame.hits,*log_frame.hits),(*ui_frame.blocked,*log_frame.blocked))
                log_hits_valid=True
            else:
                log_hits_valid=False
            tooltip=()
            ui_hover=next((hit for hit in reversed(ui_frame.hits) if hit.rect.collidepoint(mouse)),None)
            if ui_hover is not None and view_choices is not None:
                if ui_hover.verb=='family':
                    row=view_choices.all_actions[families[ui_hover.index].indices[0]]
                    tooltip=(row.display_name,variant_label(row),cost_label(row),row.description,
                        row.availability_status.value.replace('_',' ') if not row.valid_targets else '')
                elif ui_hover.verb=='variant':
                    row=view_choices.all_actions[ui_hover.index]
                    tooltip=(row.display_name,variant_label(row),cost_label(row),row.description,
                        row.availability_status.value.replace('_',' ') if not row.valid_targets else '')
                elif ui_hover.label:
                    tooltip=(ui_hover.label,)
            elif hover is not None:
                actor=displayed.actors.get(UUID(hover.identity)) if hover.kind=='actor' else None
                obj=displayed.objects.get(UUID(hover.identity)) if hover.kind in ('object','aperture') else None
                if actor is not None:
                    tooltip=(actor.name,f'HP {shown_hp.get(str(actor.uuid),actor.normal_hp)}/{actor.maximum_hp} · AC {actor.armor_class}')
                elif obj is not None:
                    options=world_options(choices,hover) if choices is not None else ()
                    tooltip=(obj.item.name,*tuple(option.label+(f' · {option.reason}' if option.reason else '') for option in options))
            tooltip=tuple(line for line in tooltip if line)
            if tooltip!=tooltip_lines:
                tooltip_lines=tooltip;hover_since=ui_elapsed_ms
            tooltip_point=(mouse[0]+round(16*geometry.scale),mouse[1]+round(20*geometry.scale))
            if focus_ui.pinned_tooltip:
                draw_tooltip(screen,geometry,ui_fonts,skin,focus_ui.pinned_tooltip,focus_ui.tooltip_position)
            elif ui_elapsed_ms-hover_since>=350:
                draw_tooltip(screen,geometry,ui_fonts,skin,tooltip_lines,tooltip_point)
            pygame.display.flip()
            if collect_frames:
                frames.append(GameFrame(
                    frame, latest.reducer_cursor, historical.reducer_cursor, len(pending),
                    active.root.uuid if active is not None else None, elapsed_ms, paused, ready and not paused,
                    tuple((actor.contact.actor_uuid, actor.contact.grid) for actor in actors),
                    tuple((actor.contact.actor_uuid, shown_hp.get(actor.contact.actor_uuid, actor.contact.hp)) for actor in actors),
                ))
            if capture_dir is not None and (frame % capture_every == 0 or complete):
                pygame.image.save(screen, capture_dir / f"frame-{frame:05}.png")
            if active is not None and complete and not paused:
                historical = after
                assert active_group is not None
                settled = tuple(row for rows, owner in log_pending if owner == active_group.primary.root.uuid for row in rows)
                if settled:
                    log_history=retain_logs(log_history,append_log_rows(settled,reveal_ms=presentation_ms))
                    log_pending[:] = [(rows, owner) for rows, owner in log_pending if owner != active_group.primary.root.uuid]
                active = None
                active_group = None
                choreography = None
                motion = None
            frame += 1
            if (stop_after_commands is not None and issued >= stop_after_commands
                    and active is None and not pending and (waiting_for_player or encounter_ended)):
                break
            if exit_when_ended and encounter_ended and active is None and not pending:
                break
        return GameSummary(latest, historical, tuple(frames), tuple(retained), issued, tuple(gaps), encounter_ended,
                           restart_requested)
    finally:
        close_session(session)
        pygame.quit()


def run(
    *, encounter_id: str | None = None, frame_deltas: Sequence[float] | None = None,
    frame_events: Mapping[int, Sequence[pygame.event.Event]] | None = None,
    max_frames: int | None = None, window_size: tuple[int, int] = (1280, 800), quadrant: int = 0,
    capture_dir: Path | None = None, player_input: PlayerInput | None = None,
    capture_every: int = 6,
    stop_after_commands: int | None = None,
    exit_when_ended: bool = False, collect_frames: bool = False,
    player_builds: tuple[CharacterBuild,...] | None = None, fullscreen: bool = False,
    player_positions: tuple[tuple[int, int], tuple[int, int]] = ((10, 10), (10, 12)),
    enemy_positions: tuple[tuple[int, int], tuple[int, int]] = ((14, 10), (14, 12)),
) -> GameSummary:
    """Run real Pygame input, or the same command boundary with deterministic inputs."""
    if frame_deltas is not None and (not frame_deltas or any(delta <= 0 for delta in frame_deltas)):
        raise ValueError("frame deltas must be positive")
    if capture_every < 1:
        raise ValueError("capture cadence must be positive")
    return asyncio.run(_run(
        frame_deltas=frame_deltas, frame_events=frame_events or {}, max_frames=max_frames,
        window_size=window_size, quadrant=quadrant, capture_dir=capture_dir,
        player_input=player_input, capture_every=capture_every, stop_after_commands=stop_after_commands,
        exit_when_ended=exit_when_ended, collect_frames=collect_frames, encounter_id=encounter_id,
        player_positions=player_positions, enemy_positions=enemy_positions,player_builds=player_builds,fullscreen=fullscreen,
    ))
