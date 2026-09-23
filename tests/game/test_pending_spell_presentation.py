"""Real saved spell stories retain timing, geometry and observer boundaries."""

from math import hypot
from uuid import UUID

import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.animation import ProjectileSample, body_clip, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.area_media import AreaMedia
from game.attack import BoundAttack
from game.cast_media import cast_media_draw_commands
from game.choreography import bind_choreography, bind_motion, sample_choreography, sample_motion
from game.combat import BoundCast
from game.motion_media import bind_motion_media, motion_media_draw_commands
from game.player_facts import ActionFact, DamageFact, MovementFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.stationary_media import stationary_media_draw_commands
from tests.game.pending_spell_scenarios import pending_spell_history


CASES = (
    ("inflict_wounds", {}), ("inflict_wounds", {"miss": True}),
    ("hellish_rebuke", {}), ("hellish_rebuke", {"saved": True}),
    ("shatter", {}), ("shatter", {"blocked": True}), ("shatter", {"raised": True}),
    ("misty_step", {}), ("misty_step", {"perspective": "departure"}),
    ("misty_step", {"perspective": "arrival"}),
    ("bless", {}), ("bane", {}),
    ("false_life", {}), ("false_life", {"replace_grant": True}),
    ("jump", {}), ("jump", {"long_jump": True}), ("jump", {"raised": True}),
    ("expeditious_retreat", {}), ("haste", {}),
)


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module")
def histories():
    retained = {}

    def capture(program, **options):
        key = program, tuple(sorted(options.items()))
        if key not in retained:
            retained[key] = pending_spell_history(program=program, **options)
        return retained[key]

    return capture


@pytest.fixture(scope="module")
def graphics():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield
    pygame.quit()


def heads(history, role="caster"):
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
    for root in roots:
        yield state, root
        state = reduce_lineage(state, root)


def spell_head(history, spell, role="caster"):
    return next((state, root) for state, root in heads(history, role)
                if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell." + spell)


def motions(history, data):
    return tuple(motion for state, root in heads(history)
                 if isinstance(root.root.fact, MovementFact)
                 and (motion := bind_motion(state, root, data)) is not None)


@pytest.mark.parametrize("program,options", CASES,
    ids=[name + "-" + "-".join(options) for name, options in CASES])
def test_every_real_story_binds_and_seeks_without_native_runtime(data, histories, program, options):
    history = histories(program, **options)
    for role in history.views:
        for state, root in heads(history, role):
            if isinstance(root.root.fact, MovementFact):
                motion = bind_motion(state, root, data)
                assert motion is not None
                assert not [gap for reaction in motion.reactions for gap in reaction.choreography.gaps]
                middle = sample_motion(motion, data, motion.complete_ms / 2)
                sample_motion(motion, data, motion.complete_ms)
                assert sample_motion(motion, data, motion.complete_ms / 2) == middle
            else:
                group = bind_choreography(state, root, data)
                assert not group.gaps, (program, role, group.gaps)
                middle = sample_choreography(group, group.complete_ms / 2)
                assert sample_choreography(group, group.complete_ms).complete
                assert sample_choreography(group, group.complete_ms / 2) == middle
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("miss", (False, True))
def test_inflict_wounds_is_a_stationary_touch_with_hit_only_target_media(data, histories, graphics, miss):
    history = histories("inflict_wounds", miss=miss)
    for role in history.views:
        before, root = spell_head(history, "inflict_wounds", role)
        group = bind_choreography(before, root, data)
        node, = group.nodes
        assert isinstance(node.bound, BoundCast)
        timeline = node.bound.timeline
        application, = timeline.applications
        caster = timeline.source.caster
        assert caster.grid == (3, 6) and application.source.target.grid == (4, 6)
        assert application.source.hit is (not miss)
        assert not group.movements and not group.forced_movement
        for time in (0, timeline.release_ms - 1, timeline.release_ms, timeline.complete_ms):
            sample = sample_cast(timeline, time)
            assert not sample.projectiles, "a touch must not become an invented traveling projectile"
            assert timeline.source.caster.grid == caster.grid
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((4, 6))
            effect = cast_media_draw_commands(timeline, sample_cast(timeline, timeline.release_ms + 140), camera, None, {})
            assert {command.evidence[2] for command in effect} == (
                set() if miss else {"pending.inflict_wounds.back", "pending.inflict_wounds.front"})
            assert all(command.evidence[1] == (4, 6) for command in effect)
        if not miss:
            assert application.damage_start_ms == timeline.release_ms
            pending = sample_cast(timeline, timeline.release_ms - 1)
            contact = sample_cast(timeline, timeline.release_ms)
            assert next(body for body in pending.bodies if body.actor_uuid != caster.actor_uuid).clip == "Idle"
            assert next(body for body in contact.bodies if body.actor_uuid != caster.actor_uuid).clip == "TakeDamage"


@pytest.mark.parametrize("saved", (False, True))
def test_hellish_reaction_targets_actual_attacker_after_its_triggering_injury(data, histories, saved):
    history = histories("hellish_rebuke", saved=saved)
    for role in history.views:
        state, root = next((state, root) for state, root in heads(history, role)
            if any(isinstance(node.fact, ActionFact) and node.fact.behavior_id == "reaction.spell.hellish_rebuke"
                   for node in root.events))
        reaction, = [node for node in root.events if isinstance(node.fact, ActionFact)
                     and node.fact.behavior_id == "reaction.spell.hellish_rebuke"]
        assert isinstance(reaction.fact, ActionFact)
        parents = {child: node for node in root.events for child in node.children_lineages}
        descendant = reaction.lineage_uuid
        injury = None
        while descendant in parents:
            parent = parents[descendant]
            if isinstance(parent.fact, DamageFact):
                injury = parent.fact
                break
            descendant = parent.lineage_uuid
        assert injury is not None and injury.target_entity_uuid == reaction.fact.source_entity_uuid
        assert injury.source_entity_uuid == reaction.fact.target_entity_uuid
        group = bind_choreography(state, root, data)
        cast, = [node for node in group.nodes if node.event_uuid == reaction.uuid]
        assert isinstance(cast.bound, BoundCast)
        attack, = [node for node in group.nodes if isinstance(node.bound, BoundAttack)]
        assert isinstance(attack.bound, BoundAttack)
        injury_ms = attack.start_ms + attack.bound.timeline.contact_ms
        context = data.damage_context
        clip = body_clip(data, attack.bound.timeline.target, context.bodyClip)
        callback_ms = context.conditionFrame * 1000 / (clip.fps * context.bodyPlaybackSpeed)
        assert cast.start_ms == pytest.approx(injury_ms + callback_ms)
        assert injury_ms <= cast.start_ms < attack.start_ms + attack.bound.timeline.complete_ms
        timeline = cast.bound.timeline
        assert timeline.source.caster.actor_uuid == str(reaction.fact.source_entity_uuid)
        assert {application.source.target.actor_uuid for application in timeline.applications} == {
            str(reaction.fact.target_entity_uuid)}
        during = sample_choreography(group, cast.start_ms + timeline.release_ms)
        assert during.displayed.actors[reaction.fact.source_entity_uuid].normal_hp == 117
        assert timeline.applications[0].source.damage_total == (6 if saved else 12)


@pytest.mark.parametrize("options", ({}, {"blocked": True}, {"raised": True}), ids=("open", "wall", "raised"))
def test_shatter_contacts_all_native_recipients_together_at_one_area_center(data, histories, graphics, options):
    history = histories("shatter", **options)
    for role in history.views:
        state, root = spell_head(history, "shatter", role)
        assert isinstance(root.root.fact, SpellFact)
        declared = root.root.fact
        group = bind_choreography(state, root, data)
        node, = group.nodes
        assert isinstance(node.bound, BoundCast)
        timeline = node.bound.timeline
        assert timeline.source.ground_target is not None
        assert timeline.source.ground_target.grid == declared.aoe_position == (6, 6)
        assert timeline.source.ground_target.elevation_steps == (2 if options.get("raised") else 0)
        contacts = {application.damage_start_ms for application in timeline.applications}
        assert len(contacts) == 1 and None not in contacts
        footprint = declared.resolved_area_positions
        assert footprint and all(application.source.target.grid in footprint for application in timeline.applications)
        damaged = {UUID(application.source.target.actor_uuid) for application in timeline.applications}
        assert {state.actors[identity].name for identity in damaged} == (
            {"Target", "Saved"} if options.get("blocked") else {"Target", "Saved", "Behind"})
        if options.get("blocked"):
            assert (8, 6) not in footprint and node.bound.area_boundaries
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((6, 6))
            effect = cast_media_draw_commands(timeline, sample_cast(timeline, timeline.release_ms + 160),
                camera, AreaMedia(node.bound.area_boundaries), {})
            assert len(effect) == 2, "one shared area bank, not one explosion per recipient"
            assert {command.evidence[2] for command in effect} == {"pending.shatter.back", "pending.shatter.front"}
            assert all(command.evidence[1] == (6, 6) and command.volume is not None
                       and command.volume.center == (6, 6) for command in effect)


@pytest.mark.parametrize("perspective,attachments", (
    ("both", {"departure_ground", "arrival_ground"}),
    ("departure", {"departure_ground"}), ("arrival", {"arrival_ground"}),
))
def test_misty_media_contains_only_disclosed_endpoints(data, histories, graphics, perspective, attachments):
    history = histories("misty_step", perspective=perspective)
    state, root = spell_head(history, "misty_step", "witness")
    group = bind_choreography(state, root, data)
    action, = group.body_actions
    assert {cue.track.attachment for cue in group.stationary_media} == attachments
    if perspective != "both":
        assert {cue.position for cue in group.stationary_media} == {(8, 7)}
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((8, 7))
        # Both authored endpoint films may begin before contact; each stays at
        # its own granted historical coordinate when the caster relocates.
        for cue in group.stationary_media:
            assert cue.start_ms <= action.effect_ms < cue.end_ms
            first = stationary_media_draw_commands((cue,), cue.start_ms + 200, camera)
            later = stationary_media_draw_commands((cue,), cue.start_ms + 700, camera)
            assert first and later
            assert {command.evidence[1] for command in (*first, *later)} == {cue.position}
    assert EventQueue.event_cursor() == 0


def test_haste_accelerates_cast_body_and_hand_but_not_projectile_travel(data, histories):
    before, root = spell_head(histories("haste"), "fire_bolt")
    group = bind_choreography(before, root, data)
    cast, = [node.bound for node in group.nodes if isinstance(node.bound, BoundCast)]
    fast = cast.timeline
    baseline = compile_cast(data, "spell.fire_bolt", fast.source)
    assert fast.release_ms == pytest.approx(baseline.release_ms / 1.25)
    assert fast.body_end_ms == pytest.approx(baseline.body_end_ms / 1.25)
    prepare_seen = False
    for progress in (.1, .5, .9, .99):
        normal_sample = sample_cast(baseline, baseline.release_ms * progress)
        fast_sample = sample_cast(fast, fast.release_ms * progress)
        normal_body = next(body for body in normal_sample.bodies if body.actor_uuid == fast.source.caster.actor_uuid)
        fast_body = next(body for body in fast_sample.bodies if body.actor_uuid == fast.source.caster.actor_uuid)
        assert fast_body.frame == normal_body.frame
        assert fast_body.cast_layers == normal_body.cast_layers and fast_body.cast_layers
        for quick, slow in zip(fast_sample.projectiles, normal_sample.projectiles, strict=True):
            assert isinstance(quick, ProjectileSample) and isinstance(slow, ProjectileSample)
            assert (quick.phase, quick.column) == (slow.phase, slow.column)
            prepare_seen |= quick.phase == "prepare"
    assert prepare_seen
    for slow, quick in zip(baseline.applications, fast.applications, strict=True):
        assert quick.travel_end_ms - quick.travel_start_ms == pytest.approx(slow.travel_end_ms - slow.travel_start_ms)
        assert quick.from_point == slow.from_point and quick.to_point == slow.to_point


def test_haste_applies_native_double_speed_once_and_retreat_keeps_normal_speed(data, histories):
    normal = motions(histories("expeditious_retreat"), data)
    fast = motions(histories("haste"), data)
    durations = lambda selected: [(leg.end_ms - leg.start_ms) / hypot(leg.end[0] - leg.start[0], leg.end[1] - leg.start[1])
        for motion in selected for leg in motion.legs if leg.end != leg.start]
    ordinary = durations(normal)
    hasted = durations(fast)
    assert ordinary and hasted
    assert ordinary == pytest.approx([ordinary[0]] * len(ordinary))
    assert hasted == pytest.approx([ordinary[0] / 2] * len(hasted))


@pytest.mark.parametrize("options", ({}, {"long_jump": True}, {"raised": True}), ids=("short", "long", "raised"))
def test_jump_is_one_body_cycle_fitted_to_native_airtime(data, histories, options):
    motion, = motions(histories("jump", **options), data)
    leg, = motion.legs
    assert not motion.body_loops and leg.arc_height_px > 0
    frames = body_clip(data, motion.actor, motion.clip).frames
    samples = [sample_motion(motion, data, leg.start_ms + (leg.end_ms - leg.start_ms) * (index + .25) / frames)
               for index in range(frames)]
    assert all(sample.body is not None for sample in samples)
    assert [sample.body.frame for sample in samples if sample.body is not None] == list(range(frames))
    launch = sample_motion(motion, data, leg.start_ms)
    assert launch.contact is not None and launch.contact.grid == leg.start
    arrived = sample_motion(motion, data, leg.end_ms)
    assert arrived.contact is not None and arrived.contact.grid == leg.end
    assert arrived.lift_px == 0
    media = bind_motion_media(motion, data, 0)
    flight = [cue for cue in media if cue.media.track.assetId.startswith("pending.flight.")]
    assert len(flight) == 2
    assert all(cue.media.start_ms == leg.start_ms and cue.media.end_ms == leg.end_ms for cue in flight)


def test_dash_trails_remain_at_historical_contacts_after_the_actor_moves_on(data, histories, graphics):
    route = motions(histories("expeditious_retreat"), data)
    dashed = [motion for motion in route if bind_motion_media(motion, data, 0)]
    assert len(dashed) == 2
    for motion in dashed:
        media = bind_motion_media(motion, data, 0)
        cue = media[0]
        assert cue.actor is None and cue.leg is None
        camera = Camera(viewport=(640, 480)).with_focus(cue.media.position)
        first = motion_media_draw_commands((cue,), cue.media.start_ms + 200, camera)
        tail = motion_media_draw_commands((cue,), cue.media.start_ms + 1000, camera)
        assert first and tail
        assert {command.evidence[1] for command in (*first, *tail)} == {cue.media.position}
        assert motion.settled_contact is not None and motion.settled_contact.grid != cue.media.position
