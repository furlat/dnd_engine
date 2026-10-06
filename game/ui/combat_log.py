"""One bounded view of native projected logs and existing presentation clocks.

Entries are never generated here. Embedded sub_entries are summary transport;
their independently identified PlayerNodes own the visible detail rows.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace, field
from typing import Literal
from uuid import UUID

import pygame

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from game.choreography import BoundChoreography, MotionTimeline
from game.player_facts import CombatLogAppend, PlayerNode, PlayerState
from game.player_reduction import index_player_lineage
from game.presentation_group import PresentationGroup
from game.presentation_timing import presentation_milestones, presentation_dependencies
from game.ui.layout import UILayout
from game.ui.primitives import UIFonts, GOLD, MUTED, panel, text, button
from game.ui.rich_text import TextSpan, log_spans, plain_log, wrap_spans, draw_spans
from game.ui.skin import UISkin
from game.ui.types import LogKey, UIFrame, UIHit, UIVerb


@dataclass(frozen=True, slots=True)
class LogRow:
    key: LogKey
    entry: CombatLogEntry
    parent: LogKey | None
    turn_execution_id: UUID | None
    group_uuid: UUID | None
    reaction_to: LogKey | None
    source_index: int
    reveal_ms: float
    timing_basis: Literal['presentation', 'group_completion', 'operation_completion']


@dataclass(frozen=True, slots=True)
class LogHistory:
    rows: tuple[LogRow, ...] = ()
    dropped: int = 0


@dataclass(frozen=True, slots=True)
class LogView:
    collapsed: frozenset[LogKey] = frozenset()
    detailed: bool = True
    category: CombatLogEntryType | None = None
    actor_uuid: UUID | None = None
    selected: LogKey | None = None
    scroll: int = 0
    follow: bool = True
    anchor: LogKey | None = None
    anchor_offset: int = 0
    seen: frozenset[LogKey] = frozenset()
    selection_anchor: tuple[LogKey,int] | None = None
    selection_end: int = 0


@dataclass(frozen=True, slots=True)
class LogLayoutRow:
    row: LogRow
    depth: int
    context: bool
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class LogTextRegion:
    key: LogKey
    rect: pygame.Rect
    start: int
    advances: tuple[int,...]


@dataclass(slots=True)
class LogLayout:
    """At most 10k height records and 512 text layouts; no per-event surfaces."""
    signature: tuple[object, ...] = ()
    rows: tuple[LogLayoutRow, ...] = ()
    offsets: tuple[int, ...] = (0,)
    text_cache: dict[tuple[LogKey, str, int, int], tuple[tuple[TextSpan, ...], ...]] = field(default_factory=dict)
    text_regions: tuple[LogTextRegion,...] = ()
    scrollbar_track: pygame.Rect | None = None
    scrollbar_thumb: pygame.Rect | None = None
    maximum_scroll: int = 0


def group_log_rows(group: PresentationGroup, *, choreography: BoundChoreography | None = None,
                   motion: MotionTimeline | None = None, start_ms: float = 0.) -> tuple[LogRow, ...]:
    complete = choreography.complete_ms if choreography is not None else motion.complete_ms if motion is not None else 0.
    anchors: dict[UUID, list[tuple[str, str, float]]] = {}
    for mark in presentation_milestones(choreography, motion):
        for identity in (*mark.event_uuids, *mark.world_event_uuids):
            anchors.setdefault(identity, []).append((mark.family, mark.anchor, mark.at_ms))
    dependencies: dict[UUID, list[tuple[str, float]]] = {}
    for dependency in presentation_dependencies(choreography, motion):
        if dependency.owner_uuid is not None:
            dependencies.setdefault(dependency.owner_uuid, []).extend((row.reason, row.at_ms) for row in dependency.evidence)
    result = []
    primary_key = (LogKey(group.primary.generation, group.primary.observer_uuid, 'event', str(group.primary.root.uuid))
                   if group.primary.root.combat_log is not None else None)
    reactions = {lineage.root.uuid for lineage in group.reactions}
    for lineage in group.lineages:
        index = index_player_lineage(lineage)
        versions = {row.event_uuid: row.lineage_uuid for row in lineage.version_rows}
        logged = {node.lineage_uuid: node for node in lineage.events if node.combat_log is not None}

        def parent(node: PlayerNode) -> PlayerNode | None:
            identity = node.parent_lineage or (versions.get(node.parent_event) if node.parent_event is not None else None)
            return index.by_lineage.get(identity) if identity is not None else None

        def log_parent(node: PlayerNode) -> PlayerNode | None:
            seen = {node.lineage_uuid}
            current = parent(node)
            while current is not None:
                if current.lineage_uuid in seen:
                    raise ValueError('Cyclic native log ancestry')
                seen.add(current.lineage_uuid)
                if current.lineage_uuid in logged:
                    return current
                current = parent(current)
            return None

        gates: dict[UUID, tuple[float, bool]] = {}
        children: dict[UUID, list[PlayerNode]] = {}
        for node in logged.values():
            ancestor = log_parent(node)
            if ancestor is not None:
                children.setdefault(ancestor.lineage_uuid, []).append(node)

        def gate(node: PlayerNode) -> tuple[float, bool]:
            prior = gates.get(node.uuid)
            if prior is not None:
                return prior
            assert node.combat_log is not None
            kind = node.combat_log.entry_type
            candidates = anchors.get(node.uuid, [])
            own: list[float] = []
            if kind in (CombatLogEntryType.CONDITION_APPLIED, CombatLogEntryType.CONDITION_REMOVED, CombatLogEntryType.SPATIAL_EFFECT):
                own = [at for family, anchor, at in candidates if family == 'state' and anchor == 'commit']
            elif kind in (CombatLogEntryType.DEATH, CombatLogEntryType.TURN_START, CombatLogEntryType.TURN_END):
                own = [at for family, anchor, at in candidates if (family in ('life', 'turn') and anchor == 'start') or (family == 'state' and anchor == 'commit')]
                if kind == CombatLogEntryType.DEATH:
                    pending_children = list(node.children_lineages)
                    visited = {node.lineage_uuid}
                    while pending_children:
                        identity = pending_children.pop()
                        if identity in visited:
                            continue
                        visited.add(identity)
                        child = index.by_lineage.get(identity)
                        if child is not None:
                            own.extend(at for family, anchor, at in anchors.get(child.uuid, [])
                                       if family == 'life' and anchor == 'start')
                            pending_children.extend(child.children_lineages)
            elif kind == CombatLogEntryType.MOVEMENT:
                own = [at for family, anchor, at in candidates if family == 'motion' and anchor in ('commit', 'complete')]
                own.extend(at for reason, at in dependencies.get(node.uuid, []) if reason in ('displacement_complete', 'portal_arrival', 'portal_settled', 'shove_contact'))
            else:
                own = [at for family, anchor, at in candidates if anchor in ('contact', 'hp', 'effect') or family in ('healing', 'life') and anchor == 'start']
                if node.resolution_ref is not None:
                    for applied in index.results.get(node.resolution_ref, ()):
                        own.extend(at for _, anchor, at in anchors.get(applied.uuid, []) if anchor in ('hp', 'commit'))
                if not own:
                    # A fact-less save/roll belongs to its exact native owner;
                    # another action on the same creature is never an anchor.
                    current = parent(node)
                    while current is not None and not own:
                        own = [at for _, anchor, at in anchors.get(current.uuid, []) if anchor in ('contact', 'effect', 'hp')]
                        current = parent(current)
            # Turn headings describe the boundary, not the hazards/save outcomes
            # nested beneath it. Ordinary summaries still wait for their results.
            descendants = ([] if kind in (CombatLogEntryType.TURN_START, CombatLogEntryType.TURN_END)
                           else [gate(child) for child in children.get(node.lineage_uuid, [])])
            fallback = not own
            at = max((*own, *(value for value, _ in descendants)), default=complete)
            if fallback and kind != CombatLogEntryType.MULTI_ENTITY_ACTION:
                at = max(at, complete)
            gates[node.uuid] = (at, fallback)
            return at, fallback

        for node in sorted(logged.values(), key=lambda row: index.source_order[row.uuid]):
            ancestor = log_parent(node)
            at, fallback = gate(node)
            assert node.combat_log is not None
            result.append(LogRow(LogKey(lineage.generation, lineage.observer_uuid, 'event', str(node.uuid)),
                node.combat_log, LogKey(lineage.generation, lineage.observer_uuid, 'event', str(ancestor.uuid)) if ancestor else None,
                node.turn_execution_id, group.primary.root.uuid,
                primary_key if lineage.root.uuid in reactions and ancestor is None else None,
                index.source_order[node.uuid], start_ms + at, 'group_completion' if fallback else 'presentation'))
    return tuple(result)


def append_log_rows(appends: tuple[CombatLogAppend, ...], *, reveal_ms: float) -> tuple[LogRow, ...]:
    return tuple(LogRow(LogKey(row.generation, row.observer_uuid, 'append', str(row.encounter_log_index)),
        row.entry, None, None, None, None, row.encounter_log_index, reveal_ms, 'operation_completion') for row in appends)


def retain_logs(history: LogHistory, rows: tuple[LogRow, ...], *, capacity: int = 10_000) -> LogHistory:
    indexed = {row.key: row for row in history.rows}
    added = []
    for row in rows:
        prior = indexed.get(row.key)
        if prior is not None:
            if prior != row:
                raise ValueError('Conflicting delivery for one projected combat-log identity')
            continue
        indexed[row.key] = row
        added.append(row)
    combined = (*history.rows, *added)
    removed = max(0, len(combined) - capacity)
    # Prefer evicting complete received groups. A sole oversized group is
    # trimmed in source order; absent parents are promoted only in the view.
    if removed and removed < len(combined):
        group = combined[removed-1].group_uuid
        if group is not None and any(row.group_uuid != group for row in combined[removed:]):
            while removed < len(combined) and combined[removed].group_uuid == group:
                removed += 1
    return LogHistory(tuple(combined[removed:]), history.dropped + removed)


def admitted_log_rows(history: LogHistory, now_ms: float) -> dict[LogKey, LogRow]:
    """One eligibility predicate for the tree and its unread-entry count."""
    admitted = {row.key: row for row in history.rows if row.reveal_ms <= now_ms}
    all_rows = {row.key: row for row in history.rows}
    for key, row in tuple(admitted.items()):
        ancestor = row.parent
        seen = {key}
        while ancestor in all_rows:
            if ancestor in seen:
                raise ValueError('Cyclic native log ancestry')
            seen.add(ancestor)
            if all_rows[ancestor].reveal_ms > now_ms:
                admitted.pop(key)
                break
            ancestor = all_rows[ancestor].parent
    return admitted


def visible_log_rows(history: LogHistory, view: LogView, now_ms: float) -> tuple[tuple[LogRow, int, bool], ...]:
    admitted = admitted_log_rows(history, now_ms)
    children: dict[LogKey | None, list[LogRow]] = {}
    for row in admitted.values():
        parent = row.parent if row.parent in admitted else row.reaction_to if row.reaction_to in admitted else None
        children.setdefault(parent, []).append(row)
    matches = {row.key for row in admitted.values() if (view.category is None or row.entry.entry_type == view.category)
        and (view.actor_uuid is None or str(view.actor_uuid) in (row.entry.source_uuid, row.entry.target_uuid))}
    included = set(matches)
    for key in tuple(matches):
        row = admitted[key]
        ancestor = row.parent or row.reaction_to
        while ancestor in admitted and ancestor not in included:
            included.add(ancestor)
            row = admitted[ancestor]
            ancestor = row.parent or row.reaction_to
    result = []

    def walk(key: LogKey | None, depth: int) -> None:
        for row in children.get(key, []):
            if row.key not in included:
                continue
            result.append((row, depth, row.key not in matches))
            if row.key not in view.collapsed or view.category is not None or view.actor_uuid is not None:
                walk(row.key, depth + 1)

    walk(None, 0)
    return tuple(result)


def scroll_log(view: LogView, cache: LogLayout, delta: int) -> LogView:
    scroll = max(0, view.scroll + delta)
    index = min(len(cache.rows)-1, max(0, bisect_right(cache.offsets, scroll)-1))
    return replace(view, scroll=scroll, follow=False,
        anchor=cache.rows[index].row.key if index >= 0 else None,
        anchor_offset=scroll-cache.offsets[index] if index >= 0 else 0)


def row_text(row: LogRow, view: LogView) -> str:
    return row.entry.detailed if view.detailed else row.entry.verbose


def copy_log_selection(history: LogHistory, view: LogView) -> str:
    row = next((row for row in history.rows if row.key == view.selected), None)
    if row is None:
        return ''
    value=plain_log(row_text(row,view))
    if view.selection_anchor is not None and view.selection_anchor[0]==row.key:
        start,end=sorted((view.selection_anchor[1],view.selection_end))
        if start!=end:
            return value[start:end]
    return value


def log_text_position(cache: LogLayout, point: tuple[int,int], key: LogKey | None = None) -> tuple[LogKey,int] | None:
    rows=tuple(row for row in cache.text_regions if key is None or row.key==key)
    row=next((row for row in rows if row.rect.collidepoint(point)),None)
    if row is None and key is not None and rows:
        row=min(rows,key=lambda row:abs(point[1]-row.rect.centery))
    if row is None:
        return None
    x=point[0]-row.rect.left
    index=min(range(len(row.advances)),key=lambda index:abs(row.advances[index]-x))
    return row.key,row.start+index


def drag_log_scroll(view: LogView, cache: LogLayout, y: int, thumb_offset: int = 0) -> LogView:
    track,thumb=cache.scrollbar_track,cache.scrollbar_thumb
    if track is None or thumb is None:
        return view
    fraction=min(1.,max(0.,(y-thumb_offset-track.top)/max(1,track.height-thumb.height)))
    return scroll_log(replace(view,scroll=0),cache,round(fraction*cache.maximum_scroll))


def _lines(cache: LogLayout, row: LogRow, view: LogView, font: UIFonts, width: int) -> tuple[tuple[TextSpan, ...], ...]:
    value = row_text(row, view)
    key = (row.key, value, font.small.get_height(), width)
    if key not in cache.text_cache:
        if len(cache.text_cache) >= 512:
            cache.text_cache.pop(next(iter(cache.text_cache)))
        cache.text_cache[key] = wrap_spans(log_spans(value), font.small, font.small_bold, width)
    return cache.text_cache[key]


def draw_combat_log(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                    history: LogHistory, view: LogView, cache: LogLayout, state: PlayerState,
                    *, now_ms: float, mouse: tuple[int, int]) -> tuple[UIFrame, LogView]:
    rect, scale = geometry.log, geometry.scale
    retained = frozenset(row.key for row in history.rows)
    view = replace(view, collapsed=view.collapsed & retained,
                   selected=view.selected if view.selected in retained else None,
                   seen=view.seen & retained,
                   selection_anchor=view.selection_anchor if view.selection_anchor is not None and view.selection_anchor[0] in retained else None)
    px = lambda value: round(value * scale)
    panel(screen, rect, skin, scale=scale)
    text(screen, font.body, 'Combat log', (rect.left+px(12), rect.top+px(10)))
    hits = []
    controls: tuple[tuple[UIVerb, str], ...] = (('log_filter', view.category.value.replace('_', ' ') if view.category else 'All events'),
        ('log_actor', 'Everyone' if view.actor_uuid is None else 'Selected actor'), ('log_detail', 'Detailed' if view.detailed else 'Verbose'))
    for index, (verb, label) in enumerate(controls):
        hit = UIHit(pygame.Rect(rect.left+px(9)+index*(rect.width-px(18))//3, rect.top+px(36),
            (rect.width-px(18))//3-px(3), px(26)), verb, label=label)
        hits.append(button(screen, font.small, hit, mouse, skin, scale=scale))
    content = rect.inflate(-px(20), 0)
    content.width-=px(10)
    content.top = rect.top + px(72)
    content.height = max(1, rect.bottom - px(42) - content.top)
    visible = visible_log_rows(history, view, now_ms)
    signature = (tuple((row.key, depth, context) for row, depth, context in visible), view.collapsed, view.detailed,
        content.width, font.small.get_height())
    if cache.signature != signature:
        rows = []
        offsets = [0]
        for row, depth, context in visible:
            width = max(px(60), content.width - px(18) - min(depth, 5)*px(12))
            height = len(_lines(cache, row, view, font, width))*font.small.get_linesize() + px(27)
            rows.append(LogLayoutRow(row, depth, context, width, height))
            offsets.append(offsets[-1] + height)
        cache.signature, cache.rows, cache.offsets = signature, tuple(rows), tuple(offsets)
    maximum = max(0, cache.offsets[-1] - content.height)
    anchored = next((cache.offsets[index] + view.anchor_offset for index,item in enumerate(cache.rows)
                     if item.row.key == view.anchor), view.scroll)
    scroll = maximum if view.follow else min(maximum, max(0, anchored))
    text_regions=[]
    previous_clip = screen.get_clip()
    screen.set_clip(content.clip(previous_clip))
    start = max(0, bisect_right(cache.offsets, scroll)-1)
    for index in range(start, len(cache.rows)):
        item = cache.rows[index]
        y = content.top + cache.offsets[index] - scroll
        if y >= content.bottom:
            break
        row_rect = pygame.Rect(content.left, y, content.width, item.height)
        if item.row.entry.entry_type in (CombatLogEntryType.TURN_START, CombatLogEntryType.TURN_END):
            pygame.draw.line(screen, GOLD, row_rect.topleft, row_rect.topright, max(1,px(1)))
        if item.row.key == view.selected:
            pygame.draw.rect(screen, (44, 48, 55), row_rect)
        x = content.left + min(item.depth, 5)*px(12)
        expand_rect=pygame.Rect(x,y,px(16),font.small.get_linesize())
        text(screen, font.small, '+' if item.row.key in view.collapsed else '−', expand_rect.topleft, GOLD)
        lines = _lines(cache, item.row, view, font, item.width)
        hits.append(UIHit(row_rect.clip(content), 'log_row', log_key=item.row.key))
        hits.append(UIHit(expand_rect.clip(content),'log_expand',log_key=item.row.key))
        plain=plain_log(row_text(item.row,view));cursor=0
        for line_index,line in enumerate(lines):
            value=''.join(span.text for span in line)
            start=plain.find(value,cursor)
            if start<0:
                raise ValueError('Rendered log text differs from its canonical entry')
            cursor=start+len(value)
            advances=[0]
            for span in line:
                line_font=font.small_bold if span.bold else font.small
                base=advances[-1]
                advances.extend(base+line_font.size(span.text[:i])[0] for i in range(1,len(span.text)+1))
            line_rect=pygame.Rect(x+px(16),y+line_index*font.small.get_linesize(),max(1,advances[-1]),font.small.get_linesize())
            if view.selection_anchor is not None and view.selection_anchor[0]==item.row.key:
                begin,end=sorted((view.selection_anchor[1],view.selection_end))
                left,right=max(0,begin-start),min(len(value),end-start)
                if left<right:
                    pygame.draw.rect(screen,(62,78,98),(line_rect.left+advances[left],line_rect.top,
                        advances[right]-advances[left],line_rect.height))
            if line_rect.colliderect(content):
                text_regions.append(LogTextRegion(item.row.key,line_rect,start,tuple(advances)))
                hits.append(UIHit(line_rect.clip(content),'log_text',log_key=item.row.key))
        draw_spans(screen, lines, font.small, font.small_bold, (x+px(16), y), muted=item.context)
        chip_y = y + len(lines)*font.small.get_linesize() + px(3)
        for identity, name in ((item.row.entry.source_uuid, item.row.entry.source_name), (item.row.entry.target_uuid, item.row.entry.target_name)):
            if not identity or not name:
                continue
            # Chips carry exact projected UUIDs. A historical name never grants
            # a current map location or permission to issue commands.
            actor = next((actor for actor in state.actors.values() if str(actor.uuid) == identity and actor.present), None)
            if actor is None:
                continue
            chip = pygame.Rect(x+px(16), chip_y, min(item.width, font.small.size(name)[0]+px(8)), font.small.get_linesize())
            text(screen, font.small, name, chip.topleft, MUTED)
            hits.append(UIHit(chip.clip(content), 'inspect', identity=actor.uuid, label=name))
            x += chip.width + px(8)
    screen.set_clip(previous_clip)
    cache.text_regions=tuple(text_regions)
    cache.maximum_scroll=maximum
    cache.scrollbar_track=pygame.Rect(content.right+px(3),content.top,max(3,px(6)),content.height)
    thumb_height=max(px(24),round(content.height*content.height/max(content.height,cache.offsets[-1])))
    thumb_top=content.top+round(scroll/max(1,maximum)*(content.height-thumb_height))
    cache.scrollbar_thumb=pygame.Rect(cache.scrollbar_track.left,thumb_top,cache.scrollbar_track.width,thumb_height)
    if maximum:
        pygame.draw.rect(screen,(49,56,65),cache.scrollbar_track)
        pygame.draw.rect(screen,MUTED,cache.scrollbar_thumb)
        hits.append(UIHit(cache.scrollbar_track,'log_scrollbar'))
    footer = rect.bottom-px(32)
    eligible = frozenset(admitted_log_rows(history, now_ms))
    new = len(eligible-view.seen) if not view.follow else 0
    footer_buttons: tuple[tuple[UIVerb,str],...] = (('log_follow', f'New entries ({new})' if new else 'Follow' if not view.follow else 'Following'), ('log_copy', 'Copy selection'))
    for offset, (verb, label) in enumerate(footer_buttons):
        hit = UIHit(pygame.Rect(rect.left+px(9)+offset*px(120), footer, px(115), px(24)), verb, label=label)
        hits.append(button(screen, font.small, hit, mouse, skin, scale=scale))
    if history.dropped:
        text(screen, font.small, f'{history.dropped} earlier entries removed', (rect.left+px(12), rect.top+px(66)), MUTED)
    top = min(len(cache.rows)-1, max(0,bisect_right(cache.offsets,scroll)-1))
    view = replace(view, scroll=scroll,
        anchor=cache.rows[top].row.key if top>=0 and not view.follow else None,
        anchor_offset=scroll-cache.offsets[top] if top>=0 and not view.follow else 0,
        seen=eligible if view.follow else view.seen)
    return UIFrame(tuple(hits), (rect,)), view
