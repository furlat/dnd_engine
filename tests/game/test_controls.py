"""Native prefixes become UI selections without executing mechanics."""

import random

import pygame
import pytest

from dnd.core.base_actions import TargetType
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.world_authoring import project_world_tile
from game.controls import ActionSelection, begin_targeting, append_target, confirm_targeting, undo_targeting, targeting_values
from game.ui.targeting import draw_selection_preview
from game.projection import Camera, TILE_WIDTH, project_screen
from game.session import advance_controller, close_session, create_session, discover_player_actions, preview_player_selection


@pytest.fixture(scope='module')
def menu_scene():
    random_state=random.getstate();random.seed(0)
    session=create_session()
    try:
        for _ in range(32):
            operation=advance_controller(session)
            if operation.boundary is not None and operation.boundary.status=='waiting_for_human':
                break
        actor=session.encounter.get_current_entity()
        assert actor is not None
        actions=discover_player_actions(session,actor.uuid)
        tiles=tuple(project_world_tile(tile) for position,tile in get_map().get_all_tiles().items()
                    if actor.senses.visible.get(position,False))
        camera=Camera(zoom=.75,viewport=(960,640)).with_focus(actor.position)
        yield session,actions,camera,tiles
    finally:
        close_session(session);random.setstate(random_state)


def select(scene,index,targets):
    session,actions,_,_=scene
    row=actions.all_actions[index]
    state=begin_targeting(index)
    preview=preview_player_selection(session,actions.entity_uuid,row)
    for target in targets:
        state=append_target(state,preview,target.index)
        preview=preview_player_selection(session,actions.entity_uuid,row,targeting_values(state,row))
    return state,preview


def missile_row(scene):
    return next((index,row) for index,row in enumerate(scene[1].all_actions)
        if row.target_type is TargetType.MULTI_ENTITY and row.num_projectiles==3 and row.allow_same_target is not False)


def test_explicit_confirmation_preserves_a_b_a_allocation_from_real_discovery(menu_scene):
    index,row=missile_row(menu_scene);first,second=row.valid_targets
    before=EventQueue.event_cursor()
    state,preview=select(menu_scene,index,(first,second,first))
    assert state.active and state.selected_targets==(first.index,second.index,first.index)
    assert confirm_targeting(state,preview)==ActionSelection(index,state.selected_targets)
    assert EventQueue.event_cursor()==before


@pytest.mark.parametrize('quadrant',range(4))
def test_target_preview_uses_disclosed_positions_allocation_and_visible_area(menu_scene,quadrant):
    _,actions,_,tiles=menu_scene
    index,row=missile_row(menu_scene);first,second=row.valid_targets
    camera=Camera(quadrant=quadrant,zoom=.75,viewport=(960,640)).with_focus(first.position)
    state,preview=select(menu_scene,index,(first,second,first))
    pygame.font.init();font=pygame.font.Font(None,17)
    image=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    before=EventQueue.event_cursor()
    supports={tile.position:tile for tile in tiles}
    selected=targeting_values(state,row)
    draw_selection_preview(image,preview,supports,camera,selected=selected,font=font)
    x,y=project_screen(second.position,camera)
    edge=round(x+TILE_WIDTH*camera.zoom/2),round(y)
    assert image.get_at(edge).a>0
    hidden=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    draw_selection_preview(hidden,preview,{p:t for p,t in supports.items() if p!=second.position},camera,selected=selected,font=font)
    assert hidden.get_at(edge).a==0
    other,other_preview=select(menu_scene,index,(first,second,second))
    changed=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    draw_selection_preview(changed,other_preview,supports,camera,selected=targeting_values(other,row),font=font)
    x,y=project_screen(first.position,camera)
    badge=pygame.Rect(round(x)-20,round(y)-32,40,20)
    assert pygame.image.tobytes(image.subsurface(badge),'RGBA')!=pygame.image.tobytes(changed.subsurface(badge),'RGBA')
    area_index,target=next((i,target) for i,row in enumerate(actions.all_actions) for target in row.valid_targets
        if target.affected_positions and any(p!=target.position for p in target.affected_positions))
    _,area_preview=select(menu_scene,area_index,())
    affected=next(p for p in target.affected_positions if p!=target.position)
    support=supports[affected];camera=camera.with_focus(affected,elevation_steps=support.elevation_steps)
    area=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    draw_selection_preview(area,area_preview,{affected:support},camera,hovered=target)
    x,y=project_screen(affected,camera,elevation_steps=support.elevation_steps)
    assert area.get_at((round(x+TILE_WIDTH*camera.zoom/2),round(y))).a>0
    disabled=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    draw_selection_preview(disabled,None,supports,camera)
    assert pygame.mask.from_surface(disabled).count()==0 and EventQueue.event_cursor()==before


def test_unique_target_rule_and_undo_use_native_prefix_admission(menu_scene):
    index,row=next((index,row) for index,row in enumerate(menu_scene[1].all_actions)
        if row.target_type is TargetType.MULTI_ENTITY and row.num_projectiles==2 and row.allow_same_target is False)
    first,second=row.valid_targets
    state,preview=select(menu_scene,index,(first,))
    assert append_target(state,preview,first.index).selected_targets==(first.index,)
    # These two recipients are farther apart than Acid Splash's five-foot
    # secondary range. The obsolete menu accepted that invalid pair.
    assert second not in preview.next_targets
    assert append_target(state,preview,second.index).selected_targets==(first.index,)
    assert confirm_targeting(state,preview)==ActionSelection(index,(first.index,))
    state=undo_targeting(state)
    assert state.active and not state.selected_targets


def test_unavailable_row_cannot_confirm_or_create_events(menu_scene):
    actions=menu_scene[1]
    index=next(index for index,row in enumerate(actions.all_actions) if not row.valid_targets)
    before=EventQueue.event_cursor()
    state,preview=select(menu_scene,index,())
    assert not preview.can_confirm and confirm_targeting(state,preview) is None
    assert preview.reason==actions.all_actions[index].availability_status.value.replace('_',' ')
    assert EventQueue.event_cursor()==before
