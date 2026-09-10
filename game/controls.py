"""Pygame selection of existing engine action rows and disclosed targets."""

from collections.abc import Iterable
from collections import Counter
from dataclasses import dataclass, replace

import pygame

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult, AvailableTarget, TargetType
from dnd.core.events import WorldTileState
from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH, pick_support, project_screen


@dataclass(frozen=True, slots=True)
class MenuState:
    selected_action: int = 0
    selected_targets: tuple[int, ...] = ()
    scroll: int = 0
    status: str = ""
    target_cursor: int = 0


@dataclass(frozen=True, slots=True)
class ActionSelection:
    action_index: int
    target_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EndTurn:
    pass


_ROW_HEIGHT = 24


def _rows_rect(panel: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(panel.left + 8, panel.top + 48, panel.width - 16, max(_ROW_HEIGHT, panel.height - 242))


def _end_button(panel: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(panel.left + 8, panel.bottom - 34, panel.width - 16, 26)


def _select_action(state: MenuState, index: int, count: int, panel: pygame.Rect) -> MenuState:
    index %= count
    visible = _rows_rect(panel).height // _ROW_HEIGHT
    scroll = max(0, min(state.scroll, index))
    if index >= scroll + visible:
        scroll = index - visible + 1
    return MenuState(selected_action=index, scroll=scroll)


def _choose_target(state: MenuState, action: AvailableActionInfo,
                   target: AvailableTarget) -> tuple[MenuState, ActionSelection | None]:
    if action.allow_same_target is False and target.index in state.selected_targets:
        return replace(state, status="Choose a different target."), None
    allocation = (*state.selected_targets, target.index)
    count = (action.num_projectiles or 1) if action.target_type is TargetType.MULTI_ENTITY else 1
    if len(allocation) < count:
        return replace(state, selected_targets=allocation, status=f"Selected {len(allocation)} of {count}."), None
    return replace(state, selected_targets=(), status=""), ActionSelection(state.selected_action, allocation)


def handle_menu_event(
    state: MenuState,
    event: pygame.event.Event,
    actions: AvailableActionsResult | None,
    camera: Camera,
    visible_tiles: Iterable[WorldTileState],
    *,
    panel_rect: pygame.Rect,
) -> tuple[MenuState, ActionSelection | EndTurn | None]:
    """Return a selection only; unavailable history supplies actions=None."""
    if actions is None:
        return state, None
    rows = actions.all_actions
    if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
        return replace(state, selected_targets=(), status=""), EndTurn()
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and _end_button(panel_rect).collidepoint(event.pos):
        return replace(state, selected_targets=(), status=""), EndTurn()
    if not rows:
        return state, None
    if not 0 <= state.selected_action < len(rows):
        state = _select_action(state, 0, len(rows), panel_rect)
    action = rows[state.selected_action]
    if event.type == pygame.MOUSEWHEEL and panel_rect.collidepoint(pygame.mouse.get_pos()):
        visible = _rows_rect(panel_rect).height // _ROW_HEIGHT
        return replace(state, scroll=max(0, min(len(rows) - visible, state.scroll - event.y * 3))), None
    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            return _select_action(state, state.selected_action + (-1 if event.key == pygame.K_UP else 1),
                                  len(rows), panel_rect), None
        if event.key == pygame.K_BACKSPACE:
            return replace(state, selected_targets=(), status=""), None
        if event.key == pygame.K_TAB and action.valid_targets:
            return replace(state, target_cursor=(state.target_cursor + 1) % len(action.valid_targets), status=""), None
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if not action.valid_targets:
                return replace(state, status=action.availability_status.value.replace("_", " ")), None
            return _choose_target(state, action, action.valid_targets[state.target_cursor % len(action.valid_targets)])
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        area = _rows_rect(panel_rect)
        if area.collidepoint(event.pos):
            index = state.scroll + (event.pos[1] - area.top) // _ROW_HEIGHT
            if index < len(rows):
                return _select_action(state, index, len(rows), panel_rect), None
        elif not panel_rect.collidepoint(event.pos):
            support, _ = pick_support(event.pos, camera, visible_tiles)
            if support is not None:
                for index, target in enumerate(action.valid_targets):
                    if target.position == support.position:
                        return _choose_target(replace(state, target_cursor=index), action, target)
            return replace(state, status="Choose one of this action's targets."), None
    return state, None


def _target_text(target: AvailableTarget) -> str:
    parts = [target.target_name or (str(target.position) if target.position is not None else "Self")]
    if target.target_name and target.position is not None:
        parts.append(str(target.position))
    if target.path_cost is not None:
        parts.append(f"move {target.path_cost} ft")
    elif target.distance is not None:
        parts.append(f"{target.distance} ft")
    if target.affected_count is not None:
        parts.append(f"{target.affected_count} affected")
    return " · ".join(parts)


def draw_target_preview(
    screen: pygame.Surface,
    state: MenuState,
    actions: AvailableActionsResult | None,
    camera: Camera,
    visible_tiles: Iterable[WorldTileState],
) -> None:
    """Mark only disclosed targets and area cells on retained visible supports."""
    if actions is None or not 0 <= state.selected_action < len(actions.all_actions):
        return
    targets = actions.all_actions[state.selected_action].valid_targets
    if not targets:
        return
    supports = {tile.position: tile for tile in visible_tiles}
    selected = targets[state.target_cursor % len(targets)]
    half_width, half_height = TILE_WIDTH * camera.zoom / 2, TILE_HEIGHT * camera.zoom / 2

    def diamond(position: tuple[int, int], color: tuple[int, int, int], width: int) -> None:
        if position in supports:
            x, y = project_screen(position, camera, elevation_steps=supports[position].elevation_steps)
            pygame.draw.polygon(screen, color, ((x, y - half_height), (x + half_width, y),
                                                (x, y + half_height), (x - half_width, y)), width)

    for target in targets:
        if target.position is not None:
            diamond(target.position, (85, 134, 149), 1)
    for position in selected.affected_positions or ():
        diamond(position, (204, 160, 87), 2)
    if selected.position in supports:
        tile = supports[selected.position]
        x, y = project_screen(tile.position, camera, elevation_steps=tile.elevation_steps)
        pygame.draw.ellipse(screen, (236, 223, 147),
                            (x - half_width * 0.7, y - half_height * 0.7,
                             half_width * 1.4, half_height * 1.4), 2)
    if state.selected_targets:
        counts = Counter(state.selected_targets)
        font = pygame.font.Font(None, 17)
        for target in targets:
            if target.index not in counts or target.position not in supports:
                continue
            tile = supports[target.position]
            x, y = project_screen(tile.position, camera, elevation_steps=tile.elevation_steps)
            center = round(x + half_width * 0.55), round(y - half_height * 0.55)
            pygame.draw.circle(screen, (32, 45, 62), center, 9)
            pygame.draw.circle(screen, (236, 223, 147), center, 9, 1)
            label = font.render(str(counts[target.index]), True, (255, 248, 210))
            screen.blit(label, label.get_rect(center=center))


def draw_menu(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: MenuState,
    actions: AvailableActionsResult | None,
    *,
    panel_rect: pygame.Rect,
    enabled: bool,
    actor_name: str,
    waiting_text: str = "Waiting for playback…",
) -> None:
    """Draw current disclosed choices without querying or executing mechanics."""
    previous_clip = screen.get_clip()
    screen.set_clip(panel_rect)
    pygame.draw.rect(screen, (19, 23, 32), panel_rect)
    color = (233, 231, 220) if enabled else (140, 143, 151)

    def text(value: str, y: int, tint: tuple[int, int, int] = color) -> None:
        screen.blit(font.render(value, True, tint), (panel_rect.left + 12, y))

    text(actor_name, panel_rect.top + 8)
    text(f"Movement {actions.remaining_movement} ft" if actions is not None else waiting_text,
         panel_rect.top + 27)
    area = _rows_rect(panel_rect)
    rows = actions.all_actions if actions is not None else []
    for index in range(state.scroll, min(len(rows), state.scroll + area.height // _ROW_HEIGHT)):
        row = rows[index]
        y = area.top + (index - state.scroll) * _ROW_HEIGHT
        if index == state.selected_action:
            pygame.draw.rect(screen, (53, 66, 88), (area.left, y, area.width, _ROW_HEIGHT))
        text(row.display_name, y + 2, color if row.valid_targets else (133, 137, 149))
    y = area.bottom + 8
    if rows:
        action = rows[min(state.selected_action, len(rows) - 1)]
        text(action.availability_status.value.replace("_", " ").capitalize(), y)
        costs = ", ".join(
            f"{cost.cost} {cost.cost_type.replace('_', ' ')}"
            + (f" + {cost.resource_cost} {cost.resource_name}" if cost.resource_name else "")
            for cost in action.costs
        )
        text(costs or f"{action.cost_amount} {action.cost_type.replace('_', ' ')}", y + 20)
        if action.valid_targets:
            target = action.valid_targets[state.target_cursor % len(action.valid_targets)]
            text(f"Target {state.target_cursor % len(action.valid_targets) + 1}/{len(action.valid_targets)}", y + 40)
            text(_target_text(target), y + 60)
            if action.target_type is TargetType.MULTI_ENTITY:
                text(f"Allocation {len(state.selected_targets)}/{action.num_projectiles or 1}", y + 80)
        text(state.status, y + 101, (240, 201, 128))
    text("Up/Down action · Tab target · Enter", panel_rect.bottom - 78)
    text("Click map · Backspace clear", panel_rect.bottom - 58)
    button = _end_button(panel_rect)
    pygame.draw.rect(screen, (55, 69, 89) if enabled else (38, 42, 51), button)
    text("End turn [N]", button.top + 3)
    screen.set_clip(previous_clip)
