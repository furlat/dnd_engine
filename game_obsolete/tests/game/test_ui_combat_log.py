"""The HUD keeps native wording, causal rows and the graphics outcome dates."""

from dataclasses import replace
from uuid import uuid4
from pathlib import Path

import pygame
import pytest

from dnd.core.combat_log import CombatLogEntryType
from game.animation_data import load_animation_data
from game.choreography import BoundChoreography, MotionTimeline
from game.attack import BoundAttack
from dnd.player.reduction import index_player_lineage
from game.presentation_group import presentation_groups, bind_presentation_group, reduce_presentation_group
from game.ui.combat_log import (LogHistory, LogView, LogLayout, group_log_rows, retain_logs, admitted_log_rows,
    visible_log_rows, copy_log_selection, draw_combat_log, scroll_log, log_text_position, drag_log_scroll, row_text)
from game.ui.layout import layout
from game.ui.primitives import fonts
from game.ui.rich_text import plain_log, log_spans, wrap_spans
from game.ui.skin import load_skin
from game.ui_composition import compose_ui_media
from tests.game.player_helpers import player_history
from tests.game.projectile_life_scenarios import projectile_life_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.hold_scenarios import hold_history
from tests.game.scenarios import attack_history, lifecycle_history
from game.presentation_timing import presentation_milestones
from dnd.core.life_types import LifeState


def test_log_wrap_keeps_fitting_words_whole(data):
    font=fonts(1.)
    value='Magic Missile hits Goblin 1 for 5 Force damage'
    lines=wrap_spans(log_spans(value),font.small,font.small_bold,font.small.size(value)[0])
    assert tuple(''.join(span.text for span in line) for line in lines)==(value,)


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data(rig_files=tuple(sorted(Path('game/data/rigs').glob('*.json'))))
    pygame.quit()


@pytest.fixture(scope='module')
def repeated(data):
    state, lineages = player_history(projectile_life_history(repeated=True, maximum_hp=20), role='caster')
    group, = presentation_groups(lineages)
    bound = bind_presentation_group(state, group, data, facings={}, contacts={})
    assert isinstance(bound, BoundChoreography)
    return state, group, bound, group_log_rows(group, choreography=bound)


def test_repeated_missiles_keep_each_native_damage_row_and_wait_for_final_outcome(repeated):
    _, group, bound, rows = repeated
    nodes = {str(node.uuid):node for lineage in group.lineages for node in lineage.events if node.combat_log is not None}
    assert len(rows) == len(nodes) and len({row.key for row in rows}) == len(rows)
    assert all(row.entry == nodes[row.key.identity].combat_log for row in rows)
    damage = [row for row in rows if row.entry.entry_type == CombatLogEntryType.DAMAGE_TAKEN]
    assert len(damage) == 3 and len({row.entry.compact for row in damage}) == 1
    index = index_player_lineage(group.primary)
    for row in damage:
        node = nodes[row.key.identity]
        owned = index.results[node.resolution_ref]
        dates = [owner.start_ms + application.hp_ms for owner in bound.nodes if not isinstance(owner.bound,BoundAttack)
                 for application in owner.bound.timeline.applications if application.hp_ms is not None
                 and any(result.uuid in {child.uuid for child in owned} for result in application.source.results)]
        assert dates and row.reveal_ms >= max(dates)
    history = retain_logs(LogHistory(),rows)
    assert retain_logs(history,rows) == history
    expanded = LogView()
    assert not visible_log_rows(history, expanded, min(row.reveal_ms for row in damage)-1)
    assert len(visible_log_rows(history,expanded,bound.complete_ms)) == len(rows)
    assert len(visible_log_rows(history,LogView(collapsed=frozenset(row.key for row in rows)),bound.complete_ms)) < len(rows)
    copied = copy_log_selection(history,replace(expanded,selected=damage[0].key,detailed=True))
    assert copied == plain_log(damage[0].entry.detailed)
    assert all(row.turn_execution_id is not None for row in rows)


@pytest.mark.parametrize('scenario', ('counterspell-success','counterspell-failure','condition','opportunity'))
def test_native_reaction_condition_and_movement_logs_use_the_existing_group_and_dates(data,scenario):
    if scenario.startswith('counterspell'):
        captured = interruption_history(blocker='counterspell',spell='fireball',blocked=scenario=='counterspell-success')
        role='caster'
    elif scenario=='condition':
        captured=hold_history(program='hold_person');role='caster'
    else:
        captured=attack_history('weapon.longsword',5,opportunity=True,whole_movement=True);role='hero'
    state,lineages=player_history(captured,role=role)
    all_rows=[]
    for group in presentation_groups(lineages):
        bound=bind_presentation_group(state,group,data,facings={},contacts={})
        rows=group_log_rows(group,choreography=bound if isinstance(bound,BoundChoreography) else None,
                            motion=bound if isinstance(bound,MotionTimeline) else None)
        assert len(rows)==sum(node.combat_log is not None for lineage in group.lineages for node in lineage.events)
        assert all(0 <= row.reveal_ms <= bound.complete_ms for row in rows)
        assert all(row.entry==next(node.combat_log for lineage in group.lineages for node in lineage.events
                                  if str(node.uuid)==row.key.identity) for row in rows)
        if group.reactions and group.primary.root.combat_log is not None:
            assert any(row.reaction_to is not None for row in rows)
        if scenario=='opportunity':
            history=LogHistory(rows);view=LogView(detailed=False,fold_groups=True)
            visible=visible_log_rows(history,view,bound.complete_ms)
            movement=next(row for row,_,_ in visible if row.entry.entry_type==CombatLogEntryType.MOVEMENT)
            assert len(visible)<len(rows)
            expanded=replace(view,expanded=frozenset({movement.key}))
            assert len(visible_log_rows(history,expanded,bound.complete_ms))>len(visible)
            assert row_text(movement,expanded)==movement.entry.compact
            detailed=replace(expanded,details=frozenset({movement.key}))
            assert row_text(movement,detailed)==movement.entry.detailed
            assert all(any(shown.key==row.key for shown,_,_ in visible) for row in rows if row.reaction_to is not None)
        if scenario=='condition':
            conditions=[row for row in rows if row.actor_condition]
            visible=visible_log_rows(LogHistory(rows),LogView(detailed=False,fold_groups=True),bound.complete_ms)
            assert all(any(shown.key==row.key for shown,_,_ in visible) for row in conditions)
        all_rows.extend(rows)
        state=reduce_presentation_group(state,group)
    assert all_rows
    if scenario=='condition':
        assert any(row.actor_condition for row in all_rows)


def test_safe_native_markup_and_measured_wrap_preserve_readable_text():
    pygame.font.init()
    font=fonts(1.)
    value='{cyan:Hero} hits **Goblin**\n  {bold red:7} damage → {unknown:unchanged} {{red:literal}}'
    expected='Hero hits Goblin\n  7 damage → {unknown:unchanged} {{red:literal}}'
    assert plain_log(value)==expected
    lines=wrap_spans(log_spans(value),font.small,font.small_bold,90)
    assert ''.join(span.text for line in lines for span in line)==expected.replace('\n','')
    assert all(sum((font.small_bold if span.bold else font.small).size(span.text)[0] for span in line)<=100 for line in lines)


def test_history_eviction_preserves_native_rows_and_promotes_only_in_the_view(repeated):
    _,_,_,native=repeated
    first=native[0]
    groups=tuple(replace(first,key=replace(first.key,identity=str(uuid4())),parent=None,
                         reaction_to=None,group_uuid=uuid4(),reveal_ms=0.) for _ in range(10_005))
    history=retain_logs(LogHistory(),groups)
    assert len(history.rows)==10_000 and history.dropped==5
    assert history.rows==groups[5:]
    assert retain_logs(history,groups[-10:])==history
    child=replace(native[-1],parent=first.key,reaction_to=None,reveal_ms=0.)
    truncated=retain_logs(LogHistory(),(first,child),capacity=1)
    assert truncated.rows==(child,) and truncated.dropped==1
    assert visible_log_rows(truncated,LogView(),100_000)==((child,0,False),)


def test_native_child_waits_for_parent_and_reaction_can_precede_its_trigger(repeated):
    _,_,_,native=repeated
    first=replace(native[0],parent=None,reveal_ms=100.)
    child=replace(native[-1],parent=first.key,reaction_to=None,reveal_ms=10.)
    history=LogHistory((first,child))
    assert not visible_log_rows(history,LogView(),50.)
    assert not admitted_log_rows(history,50.)
    assert len(visible_log_rows(history,LogView(),101.))==2
    reaction=replace(child,parent=None,reaction_to=first.key)
    assert visible_log_rows(LogHistory((first,reaction)),LogView(),50.)==((reaction,0,False),)


@pytest.mark.parametrize('scenario',('natural20','death'))
def test_turn_save_and_death_logs_follow_their_exact_native_lifecycle(data,scenario):
    captured=lifecycle_history(save_seeds=(5,)) if scenario=='natural20' else projectile_life_history(LifeState.DYING)
    state,lineages=player_history(captured,role='caster' if scenario=='death' else None)
    checked=False
    for group in presentation_groups(lineages):
        bound=bind_presentation_group(state,group,data,facings={},contacts={})
        assert isinstance(bound,BoundChoreography)
        rows=group_log_rows(group,choreography=bound)
        marks=presentation_milestones(bound)
        expected=CombatLogEntryType.SAVING_THROW if scenario=='natural20' else CombatLogEntryType.DEATH
        for row in rows:
            if row.entry.entry_type!=expected:
                continue
            dates=[mark.at_ms for mark in marks if mark.family=='life' and mark.anchor=='start']
            assert dates and row.reveal_ms==min(dates) and row.timing_basis=='presentation'
            expanded=LogView()
            visible=visible_log_rows(LogHistory(rows),expanded,
                row.reveal_ms if scenario=='natural20' else bound.complete_ms)
            assert any(item.key==row.key for item,_,_ in visible)
            checked=True
        state=reduce_presentation_group(state,group)
    assert checked


def test_unrevealed_eviction_does_not_create_an_unread_badge(repeated):
    state,_,_,native=repeated
    first=replace(native[0],parent=None,reveal_ms=100.)
    child=replace(native[-1],parent=first.key,reveal_ms=10.)
    history=retain_logs(LogHistory(),(first,child),capacity=1)
    screen=pygame.Surface((1280,720));cache=LogLayout()
    frame,view=draw_combat_log(screen,layout(screen.size),fonts(1.),load_skin(compose_ui_media().resources),
        history,LogView(follow=False),cache,state,now_ms=0.,mouse=(-1,-1))
    assert all(hit.label!='New entries (1)' for hit in frame.hits)
    assert not view.seen


def test_reading_anchor_survives_resize_and_new_rows_without_scrolling_to_latest(repeated):
    state,_,_,native=repeated
    pygame.font.init()
    skin=load_skin(compose_ui_media().resources)
    row=native[0]
    rows=tuple(replace(row,key=replace(row.key,identity=str(uuid4())),parent=None,reaction_to=None,
                       group_uuid=uuid4(),reveal_ms=0.) for _ in range(100))
    history=LogHistory(rows)
    cache=LogLayout()
    screen=pygame.Surface((1280,720))
    _,view=draw_combat_log(screen,layout(screen.size),fonts(1.),skin,history,LogView(),cache,state,now_ms=1.,mouse=(-1,-1))
    view=scroll_log(view,cache,-600)
    _,view=draw_combat_log(screen,layout(screen.size),fonts(1.),skin,history,view,cache,state,now_ms=1.,mouse=(-1,-1))
    anchor=view.anchor
    grown=retain_logs(history,(replace(rows[-1],key=replace(row.key,identity=str(uuid4()))),))
    screen=pygame.Surface((1920,1080))
    _,after=draw_combat_log(screen,layout(screen.size),fonts(1.5),skin,grown,view,cache,state,now_ms=1.,mouse=(-1,-1))
    assert not after.follow and after.anchor==anchor and after.seen==view.seen
    assert len(cache.text_cache)<=512 and len(cache.rows)<=10_000


def test_rendered_log_text_selection_copies_canonical_characters_and_scrollbar_reaches_both_ends(repeated):
    state,_,_,native=repeated
    pygame.font.init()
    skin=load_skin(compose_ui_media().resources)
    row=native[0]
    rows=tuple(replace(row,key=replace(row.key,identity=str(uuid4())),parent=None,reaction_to=None,
        group_uuid=uuid4(),reveal_ms=0.) for _ in range(80))
    history=LogHistory(rows);cache=LogLayout();screen=pygame.Surface((1280,720))
    _,view=draw_combat_log(screen,layout(screen.size),fonts(1.),skin,history,LogView(follow=False),cache,state,now_ms=1.,mouse=(-1,-1))
    region=next(region for region in cache.text_regions if len(region.advances)>6)
    start=log_text_position(cache,(region.rect.left+region.advances[1],region.rect.centery))
    end=log_text_position(cache,(region.rect.left+region.advances[6],region.rect.centery),region.key)
    assert start is not None and end is not None
    selected=replace(view,selected=region.key,selection_anchor=start,selection_end=end[1])
    assert copy_log_selection(history,selected)==plain_log(row.entry.compact)[start[1]:end[1]]
    bottom=drag_log_scroll(view,cache,cache.scrollbar_track.bottom,0)
    assert not bottom.follow and bottom.scroll==cache.maximum_scroll
    top=drag_log_scroll(bottom,cache,cache.scrollbar_track.top,0)
    assert top.scroll==0 and top.anchor==rows[0].key


def test_recorded_dice_and_modifiers_are_visible_before_expanding_children(repeated):
    _,_,_,rows=repeated
    view=LogView()
    assert len(visible_log_rows(LogHistory(rows),view,100_000))==len(rows)
    assert all(row_text(row,view)==row.entry.detailed for row in rows)
    assert all(row_text(row,replace(view,detailed=False))==row.entry.compact for row in rows)


def test_compact_copy_keeps_native_outcomes_and_obeys_reveal_gate(repeated):
    _,_,bound,rows=repeated
    history=LogHistory(rows)
    view=LogView(detailed=False,fold_groups=True)
    visible=visible_log_rows(history,view,bound.complete_ms)
    assert visible and len(visible)<len(rows)
    outcomes=[row for row,_,_ in visible if row.entry.entry_type==CombatLogEntryType.SPELL_DAMAGE]
    assert len(outcomes)==3  # All repeated missiles remain, with application details folded.
    opened=replace(view,expanded=frozenset(row.key for row in rows))
    assert len(visible_log_rows(history,opened,bound.complete_ms))==len(rows)
    assert copy_log_selection(history,view,now_ms=-1)==''
    copied=copy_log_selection(history,view,now_ms=bound.complete_ms)
    assert copied=='\n'.join('  '*depth+plain_log(row.entry.compact) for row,depth,_ in visible)
    assert not any(row.entry.entry_type==CombatLogEntryType.CONDITION_APPLIED and not row.actor_condition for row,_,_ in visible)
    selected=replace(view,selected=outcomes[0].key,category=CombatLogEntryType.TURN_START)
    assert copy_log_selection(history,selected,now_ms=bound.complete_ms)==''
