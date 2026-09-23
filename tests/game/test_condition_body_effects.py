"""Saved native owners drive size, live copies and actual historical body trails."""

from dataclasses import replace

import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from dnd.spells.conjuration import MistyStep
from dnd.spells.illusion import Blur
from dnd.spells.transmutation import EnlargeReduce
from game.animation import actor_point_offset, BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, pose_attachment_anchors
from game.body_history import retain_body_head, sample_body_trails
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography, bind_motion, sample_choreography
from game.choreography_draw import load_choreography_media, load_motion_media
from game.combat import actor_contact
from game.condition_animation import resolve_condition_appearance, condition_contact, sample_condition
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.player_facts import ConditionChangeFact
from game.player_reduction import decode_player_sequence, reduce_lineage, encode_player_sequence
from game.player_projection import project_sequence
from game.playback_frame import sample_playback_frame
from game.projection import Camera, project_screen, TILE_WIDTH
from game.scene import load_scene_media, scene_actors
from tests.game.test_spell14_native_facts import actors, saved_views
from tests.game.persistent_spell_scenarios import persistent_spell_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    data = load_animation_data()
    yield data, pygame.font.Font(None, 16)
    pygame.quit()


def capture_body_spell(program):
    caster, witness = actors()
    if program == "blur":
        setup_standard_actions(caster)
        register_spell(caster, Blur, caster_level=5)
        register_spell(caster, MistyStep, caster_level=5)
    start = EventQueue.event_cursor()

    def perform(behavior, position=None):
        available = get_available_actions(caster)
        choices = [(action, target) for action in available.all_actions if action.behavior_id == behavior
                   for target in action.valid_targets if position is None or target.position == position]
        assert choices, (behavior, position)
        event = execute_available_action(caster, *choices[0])
        assert event is not None and not event.canceled
        return event

    if program == "blur":
        event = perform("spell.blur")
        assert event is not None and not event.canceled
        for point in ((2, 5), (2, 6)):
            event = perform("action.move", point)
            assert event is not None and not event.canceled
        event = perform("spell.misty_step", (6, 6))
        assert event is not None and not event.canceled
        Entity.update_all_entities_senses()
        event = perform("action.move", (7, 6))
        assert event is not None and not event.canceled, (event.status_message if event else None, caster.position, caster.action_economy.current_speed())
        caster.remove_condition("Concentrating")
    else:
        event = EnlargeReduce(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             enlarge_mode=program, template=False).apply()
        assert event is not None and not event.canceled
        caster.remove_condition("Concentrating")
    return caster.uuid, saved_views((caster, witness), start)


@pytest.fixture(scope="module")
def mirror_history():
    history = persistent_spell_history(program="mirror_image")
    return history.before.observer_uuid, {role: encode_player_sequence(project_sequence(sequence))
        for role, sequence in history.views.items()}


@pytest.fixture(scope="module")
def blur_history():
    return capture_body_spell("blur")


def appearances(state, data):
    return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
            data.condition_media) for actor in state.actors.values()}


def raster(commands):
    return tuple((row.key, row.destination, row.surface.get_alpha(), pygame.image.tobytes(row.surface, "RGBA"))
                 for row in commands)


def test_saved_native_mirror_changes_stable_slots_at_attack_contact_and_fades(rendering, mirror_history):
    data, font = rendering
    identity, views = mirror_history
    for payload in views.values():
        state, heads = decode_player_sequence(payload)
        records, clock, counts = {}, 0., []
        for head in heads:
            group = bind_choreography(state, head, data)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                                    lineage=head, choreography=group)
            assert records == register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                                            lineage=head, choreography=group)
            for node in head.events:
                if isinstance(node.fact, ConditionChangeFact) and node.fact.event_type is EventType.CONDITION_STATE_CHANGED:
                    cue = next(row for row in group.conditions if row.event_uuid == node.uuid)
                    assert cue.complete_ms == cue.start_ms and cue.feedback_text is None and cue.body is None
                    incoming = sample_choreography(group, cue.start_ms - .001).displayed
                    updated = sample_choreography(group, cue.start_ms).displayed
                    old = appearances(incoming, data)[str(identity)].live_copies
                    new = appearances(updated, data)[str(identity)].live_copies
                    assert old is not None and new is not None and old.count == new.count + 1
                    fading = sample_condition_lifetimes(appearances(updated, data), records, data,
                        clock + cue.start_ms + new.recipe.dissipateMs / 2)[str(identity)].live_copies
                    assert fading is not None
                    assert fading.slots[-1] == (new.count, 1., .5)
            state = reduce_lineage(state, head)
            settled_at = clock + group.complete_ms + 2000
            resolved = sample_condition_lifetimes(appearances(state, data), records, data, settled_at)[str(identity)]
            count = resolved.live_copies.count if resolved.live_copies else 0
            counts.append(count)
            rows = {}
            media = load_scene_media(scene_actors(state, data, {}), data, body_rows=rows)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant)
                frame = sample_playback_frame(state, None, data, 0, settled_at, camera, {}, media, font, font,
                                              condition_lifetimes=records)
                copies = tuple(row for row in frame.commands if row.evidence[0] == str(identity)
                               and row.evidence[6] == "body_copy")
                assert len(copies) == count
                assert [row.evidence[-1] for row in copies] == list(range(count))
                assert len({row.key[1] for row in copies}) >= min(2, count)
                assert set(frame.displayed.actors) == set(state.actors)
                assert raster(copies) == raster(tuple(row for row in sample_playback_frame(state, None, data, 0,
                    settled_at, camera, {}, media, font, font, condition_lifetimes=records).commands
                    if row.evidence[0] == str(identity) and row.evidence[6] == "body_copy"))
            clock = settled_at
        assert list(dict.fromkeys(counts)) == [3, 2, 1, 0]


@pytest.mark.parametrize("mode,factor", (("enlarge", 1.175), ("reduce", .75)))
def test_saved_size_uses_one_transform_for_body_gear_and_every_socket(rendering, mode, factor):
    data, _ = rendering
    identity, views = capture_body_spell(mode)
    for payload in views.values():
        state, heads = decode_player_sequence(payload)
        original = actor_contact(state, state.actors[identity], data)
        group = bind_choreography(state, heads[0], data)
        after = reduce_lineage(state, heads[0])
        changed = actor_contact(after, after.actors[identity], data)
        assert changed.visual_scale == pytest.approx(original.visual_scale * factor)
        assert changed.grid == original.grid and changed.elevation_steps == original.elevation_steps
        cue = next(row for row in group.conditions if row.after_appearance.scale != row.before_appearance.scale)
        scale_duration = data.condition_recipes["condition.spell.enlarge_reduce"].application.durationMs
        for progress in (0., .25, .5, 1.):
            at = cue.start_ms + scale_duration * progress
            appearance = sample_condition(cue, at).appearance
            contact = condition_contact(changed, appearance)
            assert condition_contact(contact, appearance) == contact
            ratio = 1 + (factor - 1) * progress * progress * (3 - 2 * progress)
            for point in ((40, 30), (70, 45), (64, 90)):
                assert actor_point_offset(data, contact, point) == pytest.approx(
                    tuple(value * ratio for value in actor_point_offset(data, original, point)))
            rig = data.rigs[changed.rig_id]
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant)
                ground = project_screen(contact.grid, camera)
                base_scale = original.visual_scale * TILE_WIDTH / data.rig.TILE_W
                for facing in data.rig.FACING_ROW:
                    body = BodySample(str(identity), "Idle", 0, facing)
                    baseline = pose_attachment_anchors(rig, body, ground, base_scale, original.visual_scale_x)
                    scaled = pose_attachment_anchors(rig, body, ground, base_scale * ratio, contact.visual_scale_x)
                    for name, point in baseline.items():
                        assert scaled[name] == pytest.approx(tuple(ground[axis] + (point[axis] - ground[axis]) * ratio
                                                                  for axis in (0, 1)))
        for head in heads:
            state = reduce_lineage(state, head)
        assert actor_contact(state, state.actors[identity], data).visual_scale == original.visual_scale


def test_blur_uses_real_past_poses_across_heads_stops_and_cuts_at_teleport(rendering, blur_history):
    data, font = rendering
    identity, views = blur_history
    for payload in views.values():
        state, heads = decode_player_sequence(payload)
        history, records, clock, facings, positions = (), {}, 0., {}, {}
        trails_seen = cross_head_seen = teleport_seen = False
        descriptions = []
        for head in heads:
            after = reduce_lineage(state, head)
            motion = bind_motion(state, head, data)
            group = None if motion else bind_choreography(state, head, data)
            descriptions.append((head.root.fact, group.gaps if group else (), tuple((a.recipe_id, a.relocates, a.effect_ms) for a in group.body_actions) if group else ()))
            history = retain_body_head(history, state, after, start_ms=clock, facings=facings, positions=positions,
                                       choreography=group, motion=motion)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                                    lineage=head, choreography=group, motion=motion)
            rows = {}
            media = load_scene_media(scene_actors(state, data, facings), data, body_rows=rows)
            group_media = load_choreography_media(group, body_rows=rows) if group else None
            reaction_media = load_motion_media(motion, data, body_rows=rows) if motion else None
            # Previous animation rows are ordinarily retained by the application.
            for old in history[:-1]:
                if old.motion:
                    load_motion_media(old.motion, data, body_rows=rows)
                elif old.choreography:
                    load_choreography_media(old.choreography, body_rows=rows)
            assert motion is not None or group is not None
            duration = motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0
            for elapsed in (50., min(200., duration), duration):
                poses = sample_body_presentation(state, after, data, elapsed, clock + elapsed, facings,
                    choreography=group, motion=motion, positions=positions)
                look = sample_condition_lifetimes(appearances(poses.displayed, data), records, data, clock + elapsed)
                look = {key: replace(value, activity="move" if motion and elapsed < duration else "idle")
                        for key, value in look.items()}
                trails = sample_body_trails(history, poses, look, data, clock + elapsed)
                if motion and elapsed < duration and trails:
                    trails_seen = True
                    current = next(row for row in poses.poses if row.body.actor_uuid == str(identity))
                    assert all(row.pose.actor.contact.grid != current.actor.contact.grid for row in trails)
                    cross_head_seen |= any(row.age_ms > elapsed for row in trails)
                if elapsed == duration:
                    assert not trails
                for quadrant in range(4):
                    def draw(at):
                        return sample_playback_frame(state, after, data, at, clock + at,
                            Camera(quadrant=quadrant), facings, media, font, font,
                            choreography=group, choreography_media=group_media, motion=motion,
                            reaction_media=reaction_media, condition_lifetimes=records,
                            positions=positions, body_history=history)
                    frame = draw(elapsed)
                    draw(elapsed + 1)
                    again = draw(elapsed)
                    assert raster(frame.commands) == raster(again.commands)
                    if any(when <= clock + elapsed for when, who in history[-1].cuts if who == str(identity)):
                        teleport_seen = True
                        assert not any(row.evidence[6] == "body_trail" for row in frame.commands)
            final = sample_body_presentation(state, after, data, duration, clock + duration, facings,
                                             choreography=group, motion=motion, positions=positions)
            facings, positions = dict(final.facings), dict(final.positions)
            clock += duration
            state = after
        assert trails_seen and cross_head_seen and teleport_seen, descriptions


def test_stationary_distortion_changes_body_and_equipment_but_preserves_shadow(rendering, blur_history):
    data, _ = rendering
    identity, views = blur_history
    state, heads = decode_player_sequence(next(iter(views.values())))
    state = reduce_lineage(state, heads[0])
    actor = next(row for row in scene_actors(state, data, {}) if row.contact.actor_uuid == str(identity))
    look = resolve_condition_appearance(state.actors[identity].conditions, data.condition_recipes, data.condition_media)
    assert look.distortion is not None
    rows = load_scene_media((actor,), data)
    body = BodySample(str(identity), "Idle", 0, "S")
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant)
        ordinary = actor_draw_commands(data, body, actor.contact, actor.layers, rows, camera,
                                       condition=replace(look, distortion=None))
        first = actor_draw_commands(data, body, actor.contact, actor.layers, rows, camera,
                                   condition=replace(look, time_ms=2000.))
        later = actor_draw_commands(data, body, actor.contact, actor.layers, rows, camera,
                                   condition=replace(look, time_ms=2170.))
        def only(commands, role):
            return tuple(row for row in commands if row.evidence[6] == role)
        assert raster(only(first, "actor")) != raster(only(ordinary, "actor"))
        assert raster(only(first, "actor")) != raster(only(later, "actor"))
        assert raster(only(first, "actor_shadow")) == raster(only(ordinary, "actor_shadow"))
        assert len(only(first, "body_contour")) == len(look.distortion.contours)
        assert not only(first, "body_trail"), "Stationary effect must not invent historical movement"


def test_mirror_copies_current_held_weapon_without_recursive_effects(rendering, mirror_history):
    data, _ = rendering
    identity, views = mirror_history
    state, heads = decode_player_sequence(next(iter(views.values())))
    state = reduce_lineage(state, heads[0])
    actor = next(row for row in scene_actors(state, data, {}) if row.contact.actor_uuid == str(identity))
    look = resolve_condition_appearance(state.actors[identity].conditions, data.condition_recipes, data.condition_media)
    rows = load_scene_media((actor,), data)
    body = BodySample(str(identity), "Idle", 0, "S")
    without_weapon = tuple(layer for layer in actor.layers if layer.slot != "weapon")
    assert len(without_weapon) < len(actor.layers)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant)
        actual = actor_draw_commands(data, body, actor.contact, actor.layers, rows, camera, condition=look)
        unarmed = actor_draw_commands(data, body, actor.contact, without_weapon, rows, camera, condition=look)
        copies = tuple(row for row in actual if row.evidence[6] == "body_copy")
        assert len(copies) == 3
        assert raster(copies) != raster(tuple(row for row in unarmed if row.evidence[6] == "body_copy"))
        assert len(tuple(row for row in actual if row.evidence[6] == "actor")) == 1
