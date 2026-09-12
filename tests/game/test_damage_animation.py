"""Retained real damage samples authored timing without rerunning mechanics."""

from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from dnd.core.events import DamageAppliedEvent, LifeStateChangeEvent, SpatialChangeEvent, TakeDamageEvent
from dnd.core.life_types import LifeState
from game.animation import body_clip
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.combat import actor_contact
from game.damage import bind_damage, sample_damage
from game.presentation import lineage_branch as native_branch
from game.player_reduction import lineage_branch, reduce_lineage
from tests.game.player_helpers import player_history
from tests.game.forced_movement_scenarios import forced_movement_history
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.mark.parametrize(("maximum_hp", "death_saves", "life"), [
    (80, False, LifeState.ALIVE), (4, False, LifeState.DEAD), (4, True, LifeState.DYING),
])
def test_actual_damage_keeps_packet_and_normalized_life_facts_while_seeking(
    data: AnimationData, maximum_hp: int, death_saves: bool, life: LifeState,
) -> None:
    captured = attack_history("weapon.longsword", 17, opportunity=True,
        maximum_hp=maximum_hp, uses_death_saves=death_saves)
    before, lineage = captured.before, captured.lineages[0]
    event, = (row for row in lineage.events if isinstance(row, TakeDamageEvent))
    native = native_branch(lineage, event)
    packet, = (row for row in native.events if isinstance(row, DamageAppliedEvent))
    before, (lineage,) = player_history(captured)
    branch = lineage_branch(lineage, next(node for node in lineage.events if node.uuid == event.uuid))
    assert event.target_entity_uuid is not None
    prior = actor_contact(before, before.actors[event.target_entity_uuid], data, "NW")
    placed = replace(prior, grid=(3.25, 3), elevation_steps=2, body_lift_px=11)
    start = 650.0
    cue = bind_damage(before, branch, data, start_ms=start, contact=placed)
    assert cue is not None
    after = reduce_lineage(before, branch)
    expected = after.actors[event.target_entity_uuid]
    assert cue.event_uuid == event.uuid and cue.contact == placed
    assert cue.applied_damage == packet.applied_damage
    assert cue.resulting_hp == expected.normal_hp
    assert cue.resulting_life_state is expected.life_state is life
    changes = tuple(row for row in native.events if isinstance(row, LifeStateChangeEvent))
    assert cue.owned_life_events == frozenset(row.uuid for row in changes)
    if life is LifeState.DYING:
        assert packet.resulting_normal_hp < 0 and cue.resulting_hp == 0
    early = sample_damage(cue, cue.timing.start_ms - .001)
    assert early.body is None and early.vitals is None and not early.complete
    contact = sample_damage(cue, cue.timing.start_ms)
    assert contact.body is not None and contact.body.frame == 0
    assert contact.body.clip == ("Die" if life is LifeState.DEAD else "TakeDamage")
    assert contact.body.facing == "NW"
    committed = sample_damage(cue, cue.timing.hp_ms)
    assert committed.vitals is not None
    assert (committed.vitals.hp, committed.vitals.life_state) == (expected.normal_hp, life)
    complete = sample_damage(cue, cue.timing.end_ms)
    assert complete.complete and complete.vitals is not None and complete.vitals.flash is None
    if life is LifeState.DEAD:
        assert complete.body is not None and complete.body.clip == "Die"
        assert complete.body.frame == body_clip(data, prior, "Die").frames - 1
        assert sample_damage(cue, cue.timing.end_ms + 5000).body == complete.body
    else:
        assert complete.body is None
    assert sample_damage(cue, cue.timing.start_ms - .001) == early
    assert sample_damage(cue, cue.timing.start_ms) == contact
    assert reduce_lineage(before, branch) == after


def test_source_damage_frames_control_delayed_hp_flash_and_release(data: AnimationData) -> None:
    captured = attack_history("weapon.longsword", 17, opportunity=True)
    before, lineage = captured.before, captured.lineages[0]
    event, = (row for row in lineage.events if isinstance(row, TakeDamageEvent))
    before, (lineage,) = player_history(captured)
    branch = lineage_branch(lineage, next(node for node in lineage.events if node.uuid == event.uuid))
    authored = replace(data, damage_context=data.damage_context.model_copy(update={
        "impactDelayMs": 125.0, "numberFrame": 2, "flashFrame": 1, "bodyPlaybackSpeed": 2.0,
    }))
    cue = bind_damage(before, branch, authored, start_ms=500)
    assert cue is not None
    frame_ms = 1000 / (body_clip(authored, cue.contact, "TakeDamage").fps * 2)
    assert cue.timing.start_ms == 625
    assert cue.timing.hp_ms == pytest.approx(625 + 2 * frame_ms)
    assert cue.timing.flash_ms == pytest.approx(625 + frame_ms)
    prior = sample_damage(cue, cue.timing.hp_ms - .001)
    flashed = sample_damage(cue, cue.timing.flash_ms)
    committed = sample_damage(cue, cue.timing.hp_ms)
    assert prior.vitals is not None and prior.vitals.hp == cue.contact.hp
    assert flashed.vitals is not None and flashed.vitals.flash == cue.damage.hitFlash.color
    assert committed.vitals is not None and committed.vitals.hp == cue.resulting_hp
    assert sample_damage(cue, cue.timing.end_ms).body is None


@pytest.mark.parametrize("target_hp", [40, 4])
def test_actual_spike_entries_keep_separate_damage_and_reached_contacts(
    data: AnimationData, target_hp: Literal[4, 40],
) -> None:
    captured = forced_movement_history(
        source_position=(2, 9), target_position=(2, 10),
        battlefield_id="battlefield.standard_hazards_open", target_hp=target_hp,
    )
    before, roots = captured.before, captured.lineages
    lineage, = roots
    damages = tuple(row for row in lineage.events if isinstance(row, TakeDamageEvent))
    assert len(damages) == (2 if target_hp == 40 else 1)
    target_uuid = damages[0].target_entity_uuid
    assert target_uuid is not None
    by_lineage = {row.lineage_uuid: row for row in lineage.events}
    before, (lineage,) = player_history(captured)
    working = before
    placements = []
    for index, event in enumerate(damages):
        assert event.parent_lineage is not None
        entry = by_lineage[event.parent_lineage]
        assert isinstance(entry, SpatialChangeEvent)
        assert event.target_entity_uuid is not None
        actor = working.actors[event.target_entity_uuid]
        contact = replace(actor_contact(working, actor, data), grid=entry.position,
                          elevation_steps=working.tiles[entry.position].elevation_steps)
        branch = lineage_branch(lineage, next(node for node in lineage.events if node.uuid == event.uuid))
        cue = bind_damage(working, branch, data, start_ms=500 + index * 2000, contact=contact)
        assert cue is not None
        placements.append(cue.contact.grid)
        working = reduce_lineage(working, branch)
        sampled = sample_damage(cue, cue.timing.hp_ms)
        assert sampled.vitals is not None
        assert sampled.vitals.hp == working.actors[event.target_entity_uuid].normal_hp
        assert sampled.vitals.life_state is working.actors[event.target_entity_uuid].life_state
        if index > 0:
            assert cue.contact.hp is not None and cue.contact.hp < target_hp
    final = reduce_lineage(before, lineage)
    assert placements == ([(2, 11), (2, 12)] if target_hp == 40 else [(2, 11)])
    assert working.actors[target_uuid].normal_hp == final.actors[target_uuid].normal_hp
    assert working.actors[target_uuid].life_state is final.actors[target_uuid].life_state
