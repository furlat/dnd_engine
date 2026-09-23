"""Authored environment motion is driven by replayed public game outcomes."""

from dataclasses import replace

import numpy as np
import pygame
import pytest

from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.content.items.trap_hardware_builders import TRAP_HARDWARE_PROFILES
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from dnd.types.traps import TrapState
from game.animation import BodySample
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact
from game.environment_animation import remnant_bank
from game.environment_art import load_environment_art
from game.environment_draw import environment_command
from game.playback_frame import sample_playback_frame
from game.player_facts import MechanismActivationFact, ObjectDestroyedFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, camera_axis_vectors, camera_pose, project_screen
from game.replay import RecordedSequence
from game.scene import load_scene_media, scene_actors
from game.world_animation import WorldTransitionSample
from tests.game.door_destruction_scenarios import door_destruction_history
from tests.game.trap_hardware_scenarios import trap_hardware_history


@pytest.fixture(scope="module")
def raster():
    pygame.init()
    screen = pygame.display.set_mode((600, 450))
    catalog, data = load_catalog(), load_animation_data()
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                  for style in (data.number_style, data.badge_style))
    yield screen, catalog, SurfaceCache(catalog), data, fonts
    pygame.quit()


def _saved(native):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


def _render_head(raster, before, root):
    screen, catalog, cache, data, fonts = raster
    after = reduce_lineage(before, root)
    group = bind_choreography(before, root, data)
    rows = {}
    bodies = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})),
                              data, body_rows=rows)
    media = load_choreography_media(group, body_rows=rows)

    def render(camera, at, *, idle=False, actors=True):
        frame = sample_playback_frame(after if idle else before, None if idle else after,
            data, at, 3000, camera, {}, bodies, *fonts,
            choreography=None if idle else group, choreography_media=None if idle else media)
        evidence = draw_frame(screen, frame.displayed, catalog, cache, camera, 0,
            show_grid=False, show_debug=False, mouse_position=None,
            extra_commands=frame.commands if actors else (), world_transitions=frame.world_transitions,
            collect_evidence=True)
        assert evidence is not None and evidence.matches
        return frame, evidence.actual_draws, pygame.surfarray.array3d(screen)

    return after, group, render


def _bank_frames(draws, role, identity):
    # A geometry-depth fixture can have several painter pieces of one pose.
    return {(row[2], row[9]) for row in draws if len(row) > 9 and row[6] == role and row[0] == identity}


def test_every_native_environment_family_has_explicit_media():
    art = load_environment_art()
    assert set(DOOR_PROFILES) <= art.doors.keys()
    assert set(TRAP_HARDWARE_PROFILES) == art.traps.keys()
    for identity in DOOR_PROFILES:
        assert set(art.doors[identity].openings) == {"inward", "outward"}
        assert f"{identity}.wreck.clear" in art.wrecks
    for identity in TRAP_HARDWARE_PROFILES:
        assert {"ready", "activated"} <= art.traps[identity].destructions.keys()
        assert f"{identity}.wreck" in art.wrecks


@pytest.mark.parametrize("item_id", (
    "environment.door.fantasy_c1", "environment.door.fantasy_c3",
    "environment.door.desert_c7", "environment.door.desert_c9",
))
def test_recovered_rotated_banks_fit_the_native_east_boundary(raster, item_id):
    # The source workshop mounts E/S/W/N rows on S/W/N/E physical edges for
    # these four banks. A native east edge therefore starts with source N.
    state, _ = _saved(door_destruction_history(item_id=item_id).views["attacker"])
    identity, = (identity for identity, obj in state.objects.items() if obj.item.item_id == item_id)
    screen, catalog, cache, _, _ = raster
    for quadrant, source_pose in enumerate(("n", "e", "s", "w")):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 4))
        evidence = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
            show_debug=False, mouse_position=None, collect_evidence=True)
        assert evidence is not None
        poses = {row[8] for row in evidence.actual_draws
                 if len(row) > 9 and row[0] == identity and row[6] == "environment_door"}
        assert poses == {source_pose}


@pytest.mark.parametrize("swing", ("inward", "outward"))
def test_native_indoor_open_close_plays_all_24_poses_and_keeps_matching_endpoints(raster, swing):
    history = door_destruction_history(swing=swing)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    state, roots = _saved(history.views["attacker"])
    screen = raster[0]
    bank = load_environment_art().doors["environment.door.indoor_door_shabby"].openings[swing]
    assert bank.frame_count == 24 and bank.duration_ms == 800
    transitions = []
    for root in roots:
        after, group, render = _render_head(raster, state, root)
        changes = [change for change in group.world_transitions if change.field == "is_open"]
        if changes:
            change, = changes
            assert not group.gaps
            assert group.complete_ms >= change.start_ms + 800
            transitions.append(change.current)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=.75, viewport=screen.get_size()).with_focus((5, 4))
                for index, at in enumerate(bank.frame_times_ms):
                    _, draws, _ = render(camera, change.start_ms + at + .001, actors=False)
                    expected = index if change.current == "true" else 23 - index
                    assert _bank_frames(draws, "environment_door", change.identity) == {(bank.identity, expected)}
                _, _, settled = render(camera, group.complete_ms, actors=False)
                _, _, idle = render(camera, 0, idle=True, actors=False)
                np.testing.assert_array_equal(settled, idle)
                # Seeking backward must recover the same supplied middle pose.
                _, draws, first = render(camera, change.start_ms + 400, actors=False)
                render(camera, group.complete_ms, actors=False)
                _, repeated, sought = render(camera, change.start_ms + 400, actors=False)
                assert _bank_frames(draws, "environment_door", change.identity) == _bank_frames(
                    repeated, "environment_door", change.identity)
                np.testing.assert_array_equal(first, sought)
        state = after
    assert transitions == ["true", "false"]
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("kind,deployed", (("door", False), ("blade", False), ("crusher", True)))
def test_witnessed_destruction_plays_actual_bank_then_persists_after_seek(raster, kind, deployed):
    item_id = ("environment.door.indoor_door_shabby" if kind == "door" else
               f"environment.trap.{'swinging_blade' if kind == 'blade' else 'crusher'}.stone.workshop")
    history = (door_destruction_history(item_id=item_id, program="break-closed", raised=True)
               if kind == "door" else trap_hardware_history(item_id=item_id, deployed=deployed))
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    for native in history.views.values():
        state, roots = _saved(native)
        seen = 0
        for root in roots:
            facts = [node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
            if facts:
                fact, = facts
                after, group, render = _render_head(raster, state, root)
                assert not group.gaps
                change, = (change for change in group.world_transitions if change.field == "destruction")
                gesture, = group.body_actions
                assert change.start_ms == gesture.effect_ms
                assert fact.replacement_uuid is None
                replacement = after.objects[fact.object_uuid]
                assert replacement.item.integrity is ItemIntegrity.DESTROYED
                assert replacement.item.item_id == item_id
                assert replacement.item.remnant_state == fact.remnant_state
                bank = remnant_bank(load_environment_art(), replacement.item.item_id, fact.remnant_state,
                                    outcome=replacement.item.destruction_outcome)
                assert bank is not None and change.destruction is not None
                assert change.destruction.bank_id == bank.identity
                assert change.destruction.duration_ms == bank.duration_ms
                if kind != "door":
                    assert bank.frame_times_ms[-1] == pytest.approx(5958.333333, abs=.001)
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant, zoom=.75, viewport=raster[0].get_size()).with_focus(
                        fact.placement.position, elevation_steps=fact.placement.base_height_steps)
                    before_contact, _, _ = render(camera, change.start_ms - .001, actors=False)
                    assert fact.object_uuid in before_contact.displayed.objects
                    assert before_contact.displayed.objects[fact.object_uuid].item.integrity is ItemIntegrity.INTACT
                    for index, at in enumerate(bank.frame_times_ms):
                        contact, draws, _ = render(camera, change.start_ms + at + .001, actors=False)
                        assert contact.displayed.objects[fact.object_uuid].item.integrity is ItemIntegrity.DESTROYED
                        assert _bank_frames(draws, "environment_wreck", fact.object_uuid) == {(bank.identity, index)}
                    _, _, settled = render(camera, group.complete_ms, actors=False)
                    _, _, idle = render(camera, 0, idle=True, actors=False)
                    np.testing.assert_array_equal(settled, idle)
                    _, _, midway = render(camera, change.start_ms + bank.duration_ms / 2, actors=False)
                    render(camera, group.complete_ms, actors=False)
                    np.testing.assert_array_equal(render(camera, change.start_ms + bank.duration_ms / 2,
                                                          actors=False)[2], midway)
                seen += 1
            state = reduce_lineage(state, root)
        assert seen == 1
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("kind", ("door", "trap"))
def test_late_saved_initialization_uses_recorded_wreck_state_without_replaying_break(raster, kind):
    history = (door_destruction_history(program="break-closed", late_snapshot=True) if kind == "door" else
               trap_hardware_history(deployed=True, late_snapshot=True))
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0

    screen, catalog, cache, _, _ = raster
    for original in history.views.values():
        state, roots = _saved(original)
        assert not roots
        wreck, = (obj for obj in state.objects.values() if obj.item.integrity is ItemIntegrity.DESTROYED)
        assert wreck.item.remnant_state is not None
        if kind == "door":
            assert wreck.item.remnant_state.door_open is False
        else:
            assert wreck.item.remnant_state.mechanism_state is TrapState.ACTIVATED
        bank = remnant_bank(load_environment_art(), wreck.item.item_id, wreck.item.remnant_state,
                            outcome=wreck.item.destruction_outcome)
        assert bank is not None
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(wreck.placement.position)
            evidence = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                show_debug=False, mouse_position=None, collect_evidence=True)
            assert evidence is not None and evidence.matches
            assert _bank_frames(evidence.actual_draws, "environment_wreck", wreck.item.item_uuid) == {
                (bank.identity, bank.frame_count - 1)}
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("swing", ("inward", "outward"))
@pytest.mark.parametrize("raised", (False, True))
def test_delivered_indoor_depth_keeps_body_on_its_physical_side(raster, swing, raised):
    """A real clothed body crosses the plane; fixture pixels own their geometry depth."""
    state, roots = _saved(door_destruction_history(swing=swing, raised=raised).views["attacker"])
    screen, catalog, cache, data, _ = raster
    for root in roots:
        group = bind_choreography(state, root, data)
        changes = [row for row in group.world_transitions if row.field == "is_open"]
        state = reduce_lineage(state, root)
        if changes:
            break
    change, = changes
    obj = state.objects[change.identity]
    actor = next(actor for actor in state.actors.values() if actor.name == "Attacker")
    contact = actor_contact(state, actor, data)
    assert contact.elevation_steps == obj.placement.base_height_steps
    # Isolate this doorway from adjoining walls, which are checked separately.
    # Keep terrain in both sides of the raster comparison, including raised faces.
    state = replace(state, objects={change.identity: obj})
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact, layers, ("Idle",)),), all_facings=True)
    bank = load_environment_art().doors[obj.item.item_id].openings[swing]
    frame = 12
    transition = WorldTransitionSample(change, bank.frame_times_ms[frame] + .001)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus(
            (5.5, 4), elevation_steps=obj.placement.base_height_steps)
        north, east = camera_axis_vectors(quadrant)
        toward = np.sign(east[1]), np.sign(north[1])
        pose = camera_pose("east", quadrant)
        door = environment_command(bank, frame, identity=change.identity, position=(5, 4),
            elevation=obj.placement.base_height_steps, pose=pose, boundary_pose=pose, camera=camera,
            multiplier=(1, 1, 1))
        door_mask = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        door_mask.blit(door.surface, door.destination)
        door_alpha = pygame.surfarray.array_alpha(door_mask) == 255
        for offset in (-.6, .6):
            # Offset toward one jamb so both depth sides overlap solid pixels,
            # rather than comparing a body standing in the empty open doorway.
            current = replace(contact, grid=(5.5 + offset * toward[0] + .2 * toward[1],
                                             4 + offset * toward[1] - .2 * toward[0]))
            commands = actor_draw_commands(data, BodySample(current.actor_uuid, "Idle", 0, current.facing),
                current, layers, media, camera)
            body = next(row for row in commands if row.evidence[6] == "actor")
            body_mask = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            body_mask.blit(body.surface, body.destination)
            overlap = door_alpha & (pygame.surfarray.array_alpha(body_mask) == 255)
            assert np.any(overlap), (swing, quadrant, offset, door_mask.get_bounding_rect(), body_mask.get_bounding_rect())
            draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                show_debug=False, mouse_position=None, world_transitions=(transition,))
            bare = pygame.surfarray.array3d(screen)
            draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                show_debug=False, mouse_position=None, world_transitions=(transition,), extra_commands=commands)
            actual = pygame.surfarray.array3d(screen)
            visible = np.any(actual != bare, axis=2) & overlap
            if offset < 0:
                assert not np.any(visible), (swing, quadrant, "far body", visible.sum(), overlap.sum())
            else:
                # The door is behind this body. Removing only that door must
                # leave the overlapping body pixels identical; foreground terrain
                # keeps its own ordinary ordering in both images.
                draw_frame(screen, replace(state, objects={}), catalog, cache, camera, 0,
                    show_grid=False, show_debug=False, mouse_position=None, extra_commands=commands)
                np.testing.assert_array_equal(actual[overlap], pygame.surfarray.array3d(screen)[overlap],
                    err_msg=f"{swing}, camera {quadrant}: nearer body must cover the farther doorway")


def test_native_adjoining_walls_keep_their_physical_side_without_an_actor(raster):
    state, roots = _saved(door_destruction_history(swing="inward").views["attacker"])
    checked = 0
    for root in roots:
        after, group, render = _render_head(raster, state, root)
        changes = [row for row in group.world_transitions if row.field == "is_open"]
        if changes:
            change, = changes
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=.75, viewport=raster[0].get_size()).with_focus((5, 4))
                _, draws, _ = render(camera, change.start_ms + 400, actors=False)
                door_parts = [i for i, row in enumerate(draws)
                              if len(row) > 9 and row[0] == change.identity and row[6] == "environment_door"]
                wall_parts = [(i, row) for i, row in enumerate(draws) if len(row) > 6 and row[6] == "wall"]
                assert door_parts and wall_parts
                assert not any(row[6] == "actor" for row in draws if len(row) > 6)
                door_y = project_screen((5, 4), camera)[1]
                positions = {str(identity): obj.placement.position for identity, obj in after.objects.items()}
                for index, wall in wall_parts:
                    wall_y = project_screen(positions[str(wall[0])], camera)[1]
                    if wall_y < door_y:
                        assert index < min(door_parts), (quadrant, "far wall", wall[1])
                    else:
                        assert index > max(door_parts), (quadrant, "near wall", wall[1])
                checked += 1
            break
        state = after
    assert checked == 4


def test_native_trap_hardware_owns_one_body_during_actual_plate_activation(raster):
    history = trap_hardware_history(deployed=True)
    screen, catalog, cache, _, _ = raster
    for original in history.views.values():
        state, roots = _saved(original)
        assert state.senses is not None
        hardware_ids = {identity for identity, obj in state.objects.items()
                        if obj.item.item_id in TRAP_HARDWARE_PROFILES}
        mechanism_ids = {identity for identity, effect in state.senses.spatial_effects.items()
                         if effect.anchor_item_uuid in hardware_ids}
        assert len(hardware_ids) == len(mechanism_ids) == 2
        camera = Camera(viewport=screen.get_size()).with_focus((6, 4))
        initial = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
            show_debug=False, mouse_position=None, collect_evidence=True)
        assert initial is not None
        stages = [initial.actual_draws]
        for root in roots:
            if any(isinstance(node.fact, MechanismActivationFact) for node in root.events):
                _, group, render = _render_head(raster, state, root)
                assert not group.gaps
                first = min(change.start_ms for change in group.world_transitions if change.field == "activation")
                stages.append(render(camera, first + 450, actors=False)[1])
                break
            state = reduce_lineage(state, root)
        assert len(stages) == 2
        for draws in stages:
            assert {row[0] for row in draws if len(row) > 6 and row[6] == "environment_trap"} == hardware_ids
            assert not any(str(row[0]) in {str(identity) for identity in mechanism_ids}
                           and row[6] == "spatial_effect" for row in draws if len(row) > 6), (
                               "The anchored behavior must not draw another legacy body over its hardware")


@pytest.mark.parametrize("item_id", ("environment.door.fantasy_a1", "environment.door.indoor_door_shabby"))
def test_retained_architecture_keeps_only_its_frame_without_disclosing_leaf_state(raster, item_id):
    state, _ = _saved(door_destruction_history(item_id=item_id).views["attacker"])
    identity, = (identity for identity, obj in state.objects.items()
                  if obj.item.item_id == item_id)
    assert state.senses is not None and identity in state.senses.objects
    # The architectural frame remains, as for existing generic doors. The last
    # received leaf state grants no current leaf image or motion without contact.
    hidden = replace(state, senses=replace(state.senses,
        objects={key: value for key, value in state.senses.objects.items() if key != identity}))
    stale_open = replace(hidden, objects={**hidden.objects, identity: replace(hidden.objects[identity],
        item=replace(hidden.objects[identity].item, is_open=True))})
    screen, catalog, cache, _, _ = raster
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 4))
        retained_pixels = []
        for current, expected in ((state, True), (hidden, False), (stale_open, False)):
            evidence = draw_frame(screen, current, catalog, cache, camera, 0, show_grid=False,
                show_debug=False, mouse_position=None, collect_evidence=True)
            assert evidence is not None
            parts = {row[6] for row in evidence.actual_draws if len(row) > 6 and row[0] == identity}
            assert ("environment_door" in parts) is expected
            if not expected:
                assert "door_frame" in parts
                retained_pixels.append(pygame.surfarray.array3d(screen))
        np.testing.assert_array_equal(*retained_pixels)
