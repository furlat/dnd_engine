"""Actual weapon/OA results retain original contact timing during replay."""

import random
from dataclasses import replace
from math import hypot
from pathlib import Path

import pytest

from dnd.actions import AttackEvent, JumpEvent
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import DamageAppliedEvent, StepMovementEvent
from dnd.core.life_types import LifeState
from dnd.runtime_reset import reset_engine_runtime
from game.animation import body_clip
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.attack import attack_projectile_contact, bind_attack, project_attack_projectile, sample_attack, select_attack_profile
from game.choreography import sample_choreography
from game.combat import actor_contact
from game.motion import bind_motion, sample_motion
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH, project_world
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.mark.parametrize(("weapon", "seed", "profile", "outcome"), [
    ("weapon.longsword", 17, "melee-main", AttackOutcome.HIT),
    ("weapon.longsword", 1, "melee-main", AttackOutcome.MISS),
    ("weapon.longsword", 5, "melee-critical", AttackOutcome.CRIT),
    ("weapon.dagger", 17, "melee-piercing", AttackOutcome.HIT),
    ("weapon.mace", 17, "melee-blunt-swing", AttackOutcome.HIT),
    ("weapon.greatsword", 17, "melee-heavy-cleave", AttackOutcome.HIT),
])
def test_weapon_facts_choose_authored_profile_and_contact_feedback(
    data: AnimationData, weapon: str, seed: int, profile: str, outcome: AttackOutcome,
) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history(weapon, seed)
        assert isinstance(lineage.root, AttackEvent) and lineage.root.attack_outcome is outcome
        assert lineage.root.target_entity_uuid is not None
        bound = bind_attack(before, lineage, data, facings={str(lineage.root.target_entity_uuid): "NW"})
        assert bound is not None
        timeline = bound.timeline
        assert timeline.profile_id == profile
        assert not timeline.missing_media
        initial = sample_attack(timeline, 0)
        prior = sample_attack(timeline, timeline.contact_ms - 0.001)
        contact = sample_attack(timeline, timeline.contact_ms)
        completed = sample_attack(timeline, timeline.complete_ms)
        assert initial.bodies[0].clip == timeline.clip
        assert initial.bodies[1].facing == "NW"
        assert prior.vitals[0].hp == before.actors[lineage.root.target_entity_uuid].normal_hp
        applied = [row for row in lineage.events if isinstance(row, DamageAppliedEvent)]
        if applied:
            assert contact.vitals[0].hp == applied[0].resulting_normal_hp
            assert any(row.value == applied[0].applied_damage for row in contact.numbers)
            assert contact.bodies[1].clip == ("Die" if contact.vitals[0].life_state is LifeState.DEAD else "TakeDamage")
            assert timeline.damage_timing is not None
            assert timeline.complete_ms == max(timeline.body_end_ms, timeline.damage_timing.end_ms)
            if outcome is AttackOutcome.CRIT:
                assert contact.vitals[0].flash == data.damage_context.criticalFlashColor
        else:
            assert contact.vitals == prior.vitals
            assert [(row.value, row.label, row.kind) for row in contact.numbers] == [(None, "Miss", "badge")]
            assert timeline.complete_ms == timeline.body_end_ms
        assert completed.complete and not completed.numbers
        assert completed.vitals[0].hp == bound.after.actors[lineage.root.target_entity_uuid].normal_hp
        assert sample_attack(timeline, 0) == initial  # absolute seeking after a completed read
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


def test_real_goblin_opportunity_attack_uses_same_profile_and_preserves_pre_step_contact(data: AnimationData) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.longsword", 17, opportunity=True)
        assert isinstance(lineage.root, AttackEvent)
        assert lineage.root.behavior_id == "reaction.opportunity_attack"
        assert lineage.root.parent_lineage is not None
        bound = bind_attack(before, lineage, data)
        assert bound is not None
        timeline = bound.timeline
        assert (timeline.source.grid, timeline.target.grid) == ((4, 3), (3, 3))
        assert timeline.source.rig_id == "smallscale.goblin01"
        assert timeline.profile_id == "melee-main"
        assert timeline.contact_ms == pytest.approx(8 * 1000 / 12)
        assert timeline.body_end_ms == pytest.approx(14 * 1000 / 12)
        assert timeline.missing_media == ("smallscale.goblin01/Attack1/slash/Slash1",)
        assert sample_attack(timeline, timeline.contact_ms).bodies[0].frame == 8
        assert bound.after.senses is not None and bound.after.senses.position == (3, 3)
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


@pytest.mark.parametrize(("destination", "maximum_hp"), [
    ((2, 3), 80),  # reaction on the first orthogonal edge
    ((2, 2), 80),  # source's fixed lead time and diagonal remaining duration
    ((3, 1), 80),  # complete an earlier step before binding the provoking edge
    ((2, 3), 4),   # actual lethal reaction; the attempted edge never commits
])
def test_walk_holds_at_the_provoking_edge_and_resumes_only_committed_steps(
    data: AnimationData, destination: tuple[int, int], maximum_hp: int,
) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.longsword", 5 if maximum_hp == 4 else 17, opportunity=True,
                                  whole_movement=True, destination=destination, maximum_hp=maximum_hp)
        timeline = bind_motion(before, lineage, data)
        assert timeline is not None and len(timeline.reactions) == 1
        reaction = timeline.reactions[0]
        steps = [event for event in lineage.events if isinstance(event, StepMovementEvent)]
        attack = next(event for event in lineage.events if isinstance(event, AttackEvent))
        step = next(event for event in steps if event.lineage_uuid == attack.parent_lineage)
        fraction = min(.35, max(.12, data.movement_reaction_context.movementLeadInMs / data.movement_context.walkStepDurationMs))
        expected = tuple(start + (end - start) * fraction
                         for start, end in zip(step.from_position, step.to_position))
        held = sample_motion(timeline, data, reaction.start_ms)
        assert held.reaction is reaction.choreography and held.contact.grid == pytest.approx(expected)
        assert held.reaction_elapsed_ms == 0
        assert held.displayed_vitals[0].hp == maximum_hp
        assert attack.behavior_id is not None
        profile = select_attack_profile(data.attack_recipes[attack.behavior_id], attack)
        assert profile is not None
        source = actor_contact(before, before.actors[attack.source_entity_uuid], data)
        clip = body_clip(data, source, profile.actor.clip)
        contact_frame = next(anchor.frame for name in ("impact", "contact", "effect")
                             for anchor in profile.anchors if anchor.name == name)
        impact_at = reaction.start_ms + contact_frame * 1000 / (clip.fps * profile.actor.playbackSpeed)
        impact = sample_motion(timeline, data, impact_at)
        damage = next(event for event in lineage.events if isinstance(event, DamageAppliedEvent))
        assert impact.contact.grid == held.contact.grid
        assert impact.displayed_vitals[0].hp == damage.resulting_normal_hp
        final = sample_motion(timeline, data, timeline.complete_ms)
        assert final.complete and final.reaction is None
        assert final.displayed_vitals[0].hp == damage.resulting_normal_hp
        if step.committed:
            resumed = sample_motion(timeline, data, reaction.end_ms)
            assert resumed.reaction is None and resumed.body.frame == 0
            assert resumed.contact.grid == held.contact.grid
            assert final.contact.grid == destination
            remaining = (data.movement_context.walkStepDurationMs
                         * ((step.to_position[0] - step.from_position[0]) ** 2
                            + (step.to_position[1] - step.from_position[1]) ** 2) ** .5 * (1 - fraction))
            assert timeline.complete_ms == pytest.approx(reaction.end_ms + remaining)
            assert final.contact.life_state is LifeState.ALIVE
        else:
            assert final.contact.grid == held.contact.grid
            assert final.contact.life_state is LifeState.DEAD and final.body.clip == "Die"
            assert timeline.complete_ms == reaction.end_ms
        assert sample_motion(timeline, data, reaction.start_ms) == held
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


def test_real_diagonal_jump_uses_original_planar_distance_clock_and_arc(data: AnimationData) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.longsword", 17, opportunity=True,
            whole_movement=True, destination=(4, 4), movement_behavior="action.jump")
        assert isinstance(lineage.root, JumpEvent)
        timeline = bind_motion(before, lineage, data)
        assert timeline is not None and not timeline.reactions
        context = data.movement_context
        distance = 2 ** .5
        duration = context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs
        arc = context.jumpArcBasePx + distance * context.jumpArcPerCellPx
        assert timeline.complete_ms == pytest.approx(duration)
        middle = sample_motion(timeline, data, duration / 2)
        assert middle.contact.grid == pytest.approx((3.5, 3.5))
        assert middle.lift_px == pytest.approx(arc)
        assert middle.body.clip == context.jumpClip
        final = sample_motion(timeline, data, duration)
        assert final.complete and final.contact.grid == (4, 4) and final.lift_px == 0
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


def test_later_edge_reaction_binds_the_hp_left_by_the_earlier_attack(data: AnimationData) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.longsword", 17, opportunity=True,
            whole_movement=True, destination=(0, 3), watcher_positions=((4, 3), (2, 4)))
        timeline = bind_motion(before, lineage, data)
        assert timeline is not None and len(timeline.reactions) == 2
        first, second = timeline.reactions
        prior_result = sample_choreography(first.choreography, first.choreography.complete_ms).vitals[0]
        assert prior_result.hp is not None and prior_result.hp < 80
        assert second.contact.hp == prior_result.hp
        assert first.contact.grid[0] > 2
        assert second.contact.grid[0] < 1
        assert first.end_ms < second.start_ms
        held = sample_motion(timeline, data, second.start_ms)
        assert held.displayed_vitals[0].hp == prior_result.hp
        assert sample_motion(timeline, data, timeline.complete_ms).contact.grid == (0, 3)
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


@pytest.mark.parametrize(("goblin_source", "seed", "maximum_hp", "position", "outcome"), [
    (False, 17, 80, (7, 3), AttackOutcome.HIT),
    (False, 1, 80, (6, 6), AttackOutcome.MISS),
    (True, 17, 80, (7, 3), AttackOutcome.HIT),
    (True, 1, 80, (6, 6), AttackOutcome.MISS),
    (True, 5, 4, (7, 5), AttackOutcome.CRIT),
])
def test_real_shortbow_uses_original_release_delivery_join_and_retained_loadout(
    data: AnimationData, goblin_source: bool, seed: int, maximum_hp: int,
    position: tuple[int, int], outcome: AttackOutcome,
) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.shortbow", seed, weapon_slot=WeaponSlot.RANGED_MAIN,
            goblin_source=goblin_source, watcher_positions=(position,), maximum_hp=maximum_hp)
        assert isinstance(lineage.root, AttackEvent) and lineage.root.attack_outcome is outcome
        bound = bind_attack(before, lineage, data)
        assert bound is not None and bound.timeline.projectile is not None
        timeline, projectile = bound.timeline, bound.timeline.projectile
        assert timeline.profile_id == "ranged" and timeline.authored_clip == "Attack3"
        clock = data.rigs[data.root_rig].clips["Attack3"]
        assert timeline.release_ms == projectile.start_ms == 8 * 1000 / clock.fps
        # AnimatedEntity completes when it reaches the last frame.
        assert timeline.body_end_ms == (clock.frames - 1) * 1000 / clock.fps
        duration = max(projectile.recipe.minimumTravelDurationMs,
                       hypot(projectile.to_point[0] - projectile.from_point[0],
                             projectile.to_point[1] - projectile.from_point[1])
                       * 1000 / projectile.recipe.speedPxPerSecond)
        assert timeline.contact_ms == projectile.end_ms == pytest.approx(projectile.start_ms + duration)
        assert not sample_attack(timeline, projectile.start_ms - .001).projectiles
        released = sample_attack(timeline, projectile.start_ms)
        assert released.projectiles[0].point == projectile.from_point
        assert released.vitals[0].hp == timeline.target.hp
        arrived = sample_attack(timeline, timeline.contact_ms)
        assert not arrived.projectiles
        damage = next((event for event in lineage.events if isinstance(event, DamageAppliedEvent)), None)
        if damage is None:
            assert [(row.kind, row.label, row.value) for row in arrived.numbers] == [("badge", "Miss", None)]
            assert timeline.complete_ms == max(timeline.body_end_ms, timeline.contact_ms)
        else:
            assert arrived.vitals[0].hp == damage.resulting_normal_hp
            assert timeline.damage_timing is not None
            assert timeline.complete_ms == max(timeline.body_end_ms, timeline.damage_timing.end_ms)
            if maximum_hp == 4:
                assert arrived.vitals[0].life_state is LifeState.DEAD
        assert bound.after.actors[lineage.root.source_entity_uuid].active_weapon_set is WeaponSet.RANGED
        if goblin_source:
            assert timeline.clip == "Idle"
            assert "smallscale.goblin01/Attack3/body" in timeline.missing_media
            assert {layer.slot for layer in bound.appearances[timeline.source.actor_uuid]} == {"shadow", "body"}
        else:
            assert timeline.clip == "Attack3" and not timeline.missing_media
            assert any(layer.category == "Ranged1" for layer in bound.appearances[timeline.source.actor_uuid])

        # Held subcell contacts enter before both facing and endpoint compilation.
        held = replace(timeline.target, grid=(3.25, 4.5), elevation_steps=1.25, visual_scale=.5)
        rebound = bind_attack(before, lineage, data, contacts={held.actor_uuid: held})
        assert rebound is not None and rebound.timeline.target == held
        held_timeline = rebound.timeline
        assert held_timeline.projectile is not None
        midpoint = sample_attack(held_timeline, (held_timeline.projectile.start_ms + held_timeline.contact_ms) / 2).projectiles[0]
        for quadrant in range(4):
            effect = project_attack_projectile(held_timeline, midpoint, quadrant)
            ground, height = attack_projectile_contact(held_timeline, effect, quadrant)
            projected = project_world(ground, quadrant=quadrant, elevation_steps=height)
            factor = data.rig.TILE_W / TILE_WIDTH
            assert (projected[0] * factor, projected[1] * factor) == pytest.approx(effect.point)
            expected_height = ((held_timeline.source.elevation_steps + held.elevation_steps) / 2
                - (held_timeline.projectile.recipe.originY * held_timeline.source.visual_scale
                   + held_timeline.projectile.recipe.targetY * held.visual_scale)
                / 2 / factor / HEIGHT_STEP_PIXELS)
            assert height == pytest.approx(expected_height)
    finally:
        reset_engine_runtime()
        random.setstate(random_state)
