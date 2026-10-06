"""Render the native selection prefix; never calculate admission or AoE reach."""

from collections.abc import Mapping
from collections import Counter

import pygame

from dnd.core.base_actions import AvailableSelectionPreview, AvailableTarget, prefers_safe_movement_path
from dnd.types.event_facts import WorldTileState
from game.projection import Camera, project_screen


def position_outline(position: tuple[int, int], tiles: Mapping[tuple[int, int], WorldTileState],
                     camera: Camera) -> tuple[tuple[float, float], ...]:
    tile = tiles.get(position)
    elevation = tile.elevation_steps if tile is not None else 0
    x,y=position
    return tuple(project_screen((x+dx,y+dy),camera,elevation_steps=elevation)
        for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)))


def undisclosed_position_at(point: tuple[int, int], preview: AvailableSelectionPreview,
                           visible_tiles: Mapping[tuple[int, int], WorldTileState],
                           camera: Camera) -> tuple[int, int] | None:
    # An explicitly exposed neutral destination is selectable, but it creates no
    # world/occupant hit or label. Visible supports continue through scene picking.
    for position in preview.next_positions:
        if position in visible_tiles:
            continue
        polygon=position_outline(position, {}, camera)
        center_x=sum(x for x,_ in polygon)/4
        center_y=sum(y for _,y in polygon)/4
        dx=(max(x for x,_ in polygon)-min(x for x,_ in polygon))/2
        dy=(max(y for _,y in polygon)-min(y for _,y in polygon))/2
        if dx and dy and abs(point[0]-center_x)/dx+abs(point[1]-center_y)/dy<=1:
            return position
    return None


def draw_selection_preview(screen: pygame.Surface, preview: AvailableSelectionPreview | None,
                           tiles: Mapping[tuple[int, int], WorldTileState], camera: Camera,
                           hovered: AvailableTarget | None = None, *,
                           selected: tuple[AvailableTarget,...] = (),
                           points: tuple[tuple[int,int],...] = (),
                           font: pygame.font.Font | None = None) -> None:
    if preview is None:
        return
    for position in preview.affected_positions:
        if position in tiles:
            pygame.draw.lines(screen,(180,122,87),True,position_outline(position,tiles,camera),1)
    for position in preview.next_positions:
        pygame.draw.lines(screen,(119,164,182),True,position_outline(position,tiles,camera),1)
    for target in preview.next_targets:
        if target.position in tiles:
            assert target.position is not None
            pygame.draw.lines(screen,(119,164,182),True,position_outline(target.position,tiles,camera),1)
    for position in points:
        if position in tiles:
            pygame.draw.lines(screen,(215,185,103),True,position_outline(position,tiles,camera),2)
    for start,end in zip(points,points[1:]):
        if start in tiles and end in tiles:
            pygame.draw.line(screen,(215,185,103),project_screen(start,camera,elevation_steps=tiles[start].elevation_steps),
                project_screen(end,camera,elevation_steps=tiles[end].elevation_steps),2)
    counts=Counter(preview.effective_target_uuids)
    for target in selected:
        if target.position not in tiles:
            continue
        assert target.position is not None
        pygame.draw.lines(screen,(215,185,103),True,position_outline(target.position,tiles,camera),2)
        if font is not None and target.target_uuid is not None and target.target_uuid in counts:
            x,y=project_screen(target.position,camera,elevation_steps=tiles[target.position].elevation_steps)
            label=font.render('×'+str(counts[target.target_uuid]),True,(255,238,185))
            screen.blit(label,label.get_rect(midbottom=(round(x),round(y)-12)))
    if hovered is not None and hovered.position is not None:
        pygame.draw.lines(screen,(215,185,103),True,position_outline(hovered.position,tiles,camera),2)
        for position in hovered.affected_positions or ():
            if position in tiles:
                pygame.draw.lines(screen,(190,118,93),True,position_outline(position,tiles,camera),1)


def draw_movement_preview(screen: pygame.Surface, target: AvailableTarget, movement_remaining: int,
                          tiles: Mapping[tuple[int, int], WorldTileState], camera: Camera,
                          font: pygame.font.Font) -> None:
    safe = prefers_safe_movement_path(target, movement_remaining)
    path = target.safe_path if safe else target.path
    cost = target.safe_path_cost if safe else target.path_cost
    threats = target.safe_path_opportunity_attack_exposures if safe else target.opportunity_attack_exposures
    color = (221, 133, 89) if threats or target.is_path_hazardous and not safe else (147, 186, 154)
    # A route is already admitted/disclosed by native discovery. Hidden supports
    # have no terrain elevation to expose; draw only received visible stretches.
    for start, end in zip(path or (), (path or ())[1:]):
        if start in tiles and end in tiles:
            pygame.draw.line(screen, color, project_screen(start,camera,elevation_steps=tiles[start].elevation_steps),
                project_screen(end,camera,elevation_steps=tiles[end].elevation_steps), 2)
    for threat in threats:
        if threat.from_position in tiles:
            pygame.draw.lines(screen,color,True,position_outline(threat.from_position,tiles,camera),2)
    if target.position in tiles and cost is not None:
        assert target.position is not None
        x,y=project_screen(target.position,camera,elevation_steps=tiles[target.position].elevation_steps)
        warning = ' · Opportunity attack' if threats else ' · Hazard' if target.is_path_hazardous and not safe else ''
        label=font.render(f'{cost} ft{warning}',True,color)
        screen.blit(label,label.get_rect(midbottom=(round(x),round(y)-12)))
