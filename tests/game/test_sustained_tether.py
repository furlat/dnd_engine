"""Real retained concentration links select seekable authored cable pixels."""

from dataclasses import replace
from math import floor
from typing import cast
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from game.animation_data import load_animation_data
from game.animation_types import TetherAnimation
from game.app import draw_frame
from game.assets import AssetSpec, SurfaceCache, load_catalog
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.device_art import device_bank, load_device_art
from game.playback_frame import sample_playback_frame
from game.player_facts import ActionFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, project_screen
from game.scene import load_scene_media, scene_actors
from tests.game.web_scenarios import web_history


@pytest.fixture(scope="module")
def native_history():
    return web_history(delivery="cannon")


@pytest.fixture(scope="module")
def retained_sequences(native_history):
    return {role: decode_player_sequence(encode_player_sequence(project_sequence(native)))
            for role, native in native_history.views.items()}


@pytest.fixture(scope="module")
def retained_views(retained_sequences):
    result = {}
    for role, (state, lineages) in retained_sequences.items():
        states = [state]
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
            states.append(state)
        result[role] = states
    return result


@pytest.fixture
def raster(tmp_path):
    pygame.init()
    screen = pygame.display.set_mode((900, 600))
    # A deterministic media fixture tests the two-endpoint contract independently
    # of art revisions. Production Web media is imported separately by its owner.
    source = pygame.Surface((32, 10), pygame.SRCALPHA)
    pygame.draw.line(source, (235, 225, 220), (1, 5), (30, 5), 3)
    pygame.draw.circle(source, (220, 95, 35), (30, 5), 3)
    path = tmp_path / "cable.png"
    pygame.image.save(source, path)
    catalog = load_catalog()
    spec = AssetSpec("test.cable", path, source.get_size(), (0, 0), 1)
    catalog = replace(catalog, resources={**catalog.resources, spec.asset_id: spec},
        spatial_tethers={"spatial_effect.spell.web": TetherAnimation(
            {"E": (spec.asset_id,)}, {"E": ((1., 5.), (30., 5.))}, 12)})
    try:
        yield screen, catalog, SurfaceCache(catalog)
    finally:
        pygame.quit()


@pytest.fixture
def shipped_raster():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    catalog = load_catalog()
    try:
        yield screen, catalog, SurfaceCache(catalog)
    finally:
        pygame.quit()


def _links(state):
    assert state.senses is not None
    return {identity: effect for identity, effect in state.senses.spatial_effects.items()
            if effect.sustainer_item_uuid is not None}


def _render(state, raster, camera, *, cable=True, commands=()):
    screen, catalog, cache = raster
    selected = catalog if cable else replace(catalog, spatial_tethers={})
    evidence = draw_frame(screen, state, selected, cache, camera, 0,
        show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
        extra_commands=commands)
    assert evidence is not None and evidence.matches
    return [row for row in evidence.actual_draws if len(row) > 6 and row[6] == "sustained_tether"], pygame.surfarray.array3d(screen)


@pytest.mark.parametrize("role", ["caster", "target"])
def test_real_two_slot_casts_and_destruction_draw_and_remove_cables_from_saved_events(retained_views, raster, role):
    states = retained_views[role]
    first = next(state for state in states if len(_links(state)) == 1)
    second = next(state for state in states if len(_links(state)) == 2)
    owner = next(iter(_links(second).values())).sustainer_item_uuid
    device = second.objects[owner]
    assert device.item.current_hit_points == device.item.maximum_hit_points == 8
    assert device.item.concentration_capacity == 2
    assert len(device.item.concentration_slots) == 2
    assert {slot.spell_id for slot in device.item.concentration_slots} == {"spell.web"}
    assert not _links(states[-1]) and states[-1].objects[owner].item.integrity is ItemIntegrity.DESTROYED
    cursor = EventQueue.event_cursor()
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus((8, 5))
        rows, first_pixels = _render(first, raster, camera)
        assert {row[0] for row in rows} == set(_links(first))
        rows, second_pixels = _render(second, raster, camera)
        assert {row[0] for row in rows} == set(_links(second))
        assert {row[8] for row in rows} == {slot.slot_uuid for slot in device.item.concentration_slots}
        _, bare = _render(second, raster, camera, cable=False)
        assert np.any(second_pixels != bare), "Actual app pixels must contain the authored cable"
        art = load_device_art()[device.item.item_id]
        facing = device.placement.orientation.value.upper() if device.placement.orientation else "E"
        muzzle = device_bank(art).muzzle_pixels[quadrant][art.rows.index(facing)][0]
        support = project_screen(device.placement.position, camera,
                                 elevation_steps=device.placement.base_height_steps)
        start = tuple(support[i] + (muzzle[i] - art.anchor[i]) * art.scale * camera.zoom for i in range(2))
        for row in rows:
            effect = _links(second)[row[0]]
            assert row[10] == pytest.approx(start)
            assert row[11] == pytest.approx(project_screen(effect.anchor_position, camera,
                elevation_steps=second.tiles[effect.anchor_position].elevation_steps))
        removed, _ = _render(states[-1], raster, camera)
        assert removed == []
        _, sought = _render(first, raster, camera)
        assert np.array_equal(sought, first_pixels), "Seeking a retained state must restore exactly its links"
    assert EventQueue.event_cursor() == cursor, "Saved player replay must not execute native events"


@pytest.mark.parametrize("role", ["caster", "target"])
def test_shipped_web_cables_draw_at_gallery_scale_from_saved_links(retained_views, shipped_raster, role):
    states = retained_views[role]
    linked = next(state for state in states if len(_links(state)) == 2)
    assert not _links(states[-1])
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.35, viewport=shipped_raster[0].get_size()).with_focus((11, 5))
        rows, pixels = _render(linked, shipped_raster, camera)
        assert {row[0] for row in rows} == set(_links(linked))
        _, without_cables = _render(linked, shipped_raster, camera, cable=False)
        assert np.any(pixels != without_cables), "Delivered cable art must survive actual app composition at gallery scale"
        removed, destroyed = _render(states[-1], shipped_raster, camera)
        _, destroyed_without_cables = _render(states[-1], shipped_raster, camera, cable=False)
        assert removed == []
        assert np.array_equal(destroyed, destroyed_without_cables)


def test_tethers_require_disclosed_endpoints_and_current_slot_and_do_not_guess_partial_origin(retained_views, raster):
    state = next(state for state in retained_views["caster"] if len(_links(state)) == 1)
    identity, effect = next(iter(_links(state).items()))
    owner, anchor = effect.sustainer_item_uuid, effect.anchor_position
    assert owner is not None and anchor is not None and state.senses is not None
    camera = Camera(viewport=raster[0].get_size()).with_focus((8, 5))
    baseline, _ = _render(state, raster, camera)
    assert baseline
    obj = state.objects[owner]
    absent_slot = replace(state, objects={**state.objects, owner: replace(obj,
        item=replace(obj.item, concentration_slots=()))})
    absent_contact = replace(state, senses=replace(state.senses,
        objects={key: contact for key, contact in state.senses.objects.items() if key != owner}))
    unknown_anchor = replace(state, senses=replace(state.senses, spatial_effects={identity:
        effect.model_copy(update={"anchor_position": None, "positions": effect.positions[:2]})}))
    hidden_anchor = replace(state, senses=replace(state.senses,
        visible=state.senses.visible - {anchor}))
    for snapshot in (absent_slot, absent_contact, unknown_anchor, hidden_anchor):
        assert _render(snapshot, raster, camera)[0] == []
    hidden_cell = (6, 5)
    partial = replace(state, senses=replace(state.senses,
        visible=state.senses.visible - {hidden_cell}))
    sections, _ = _render(partial, raster, camera)
    assert sections
    positions = (cast(tuple[float, float], row[1]) for row in sections)
    assert not any((floor(x + .5), floor(y + .5)) == hidden_cell for x, y in positions)


@pytest.mark.parametrize("role", ["caster", "target"])
def test_object_attack_gesture_keeps_device_and_tethers_until_authored_strike_contact(retained_sequences, raster, role):
    before, lineages = retained_sequences[role]
    for lineage in lineages:
        fact = lineage.root.fact
        if isinstance(fact, ActionFact) and fact.behavior_id == "action.attack_object":
            break
        before = reduce_lineage(before, lineage)
    else:
        pytest.fail("The native narrative must contain an actual object attack")
    owner = lineage.root.fact.target_entity_uuid
    assert owner in before.objects and len(_links(before)) == 2
    after = reduce_lineage(before, lineage)
    data = load_animation_data()
    group = bind_choreography(before, lineage, data)
    assert not group.gaps
    gesture, = group.body_actions
    assert gesture.enabled and gesture.clip == "Attack1" and gesture.interaction_object_uuid == owner
    assert gesture.effect_ms == pytest.approx(8 * 1000 / 12)
    assert group.complete_ms > gesture.effect_ms
    body_rows = {}
    bodies = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})),
                             data, body_rows=body_rows)
    media = load_choreography_media(group, body_rows=body_rows)
    number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                              for style in (data.number_style, data.badge_style))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus((8, 5))

        def frame(time):
            return sample_playback_frame(before, after, data, time, time, camera, {}, bodies,
                number_font, badge_font, choreography=group, choreography_media=media)

        winding = frame(gesture.effect_ms - .001)
        contact = frame(gesture.effect_ms)
        actor = next(command for command in winding.commands
                     if command.evidence[6] == "actor" and command.evidence[0] == gesture.contact.actor_uuid)
        assert actor.evidence[8:10] == ("Attack1", 7)
        assert winding.displayed.objects[owner].item.integrity is ItemIntegrity.INTACT
        assert contact.displayed.objects[owner].item.integrity is ItemIntegrity.DESTROYED
        visible, pixels = _render(winding.displayed, raster, camera, commands=winding.commands)
        assert len({row[0] for row in visible}) == 2
        assert _render(contact.displayed, raster, camera, commands=contact.commands)[0] == []
        sought = frame(gesture.effect_ms - .001)
        assert np.array_equal(pixels, _render(sought.displayed, raster, camera, commands=sought.commands)[1])


def test_object_action_projection_does_not_grant_an_unknown_target_uuid(native_history):
    native = native_history.views["target"]
    root = native.lineages[-1]
    hidden_identity = uuid4()
    # Exercise the saved-event projection boundary with an undisclosed target.
    # Only the target reference changes; neither observation nor world packets
    # grant this identity. This control is not a new native gameplay narrative.
    hidden_root = root.root.model_copy(update={"target_entity_uuid": hidden_identity})
    changed = replace(root, root=hidden_root,
        events=tuple(hidden_root if event.uuid == root.root.uuid else event for event in root.events))
    packet = encode_player_sequence(project_sequence(native.model_copy(update={
        "lineages": (*native.lineages[:-1], changed),
    })))
    _, lineages = decode_player_sequence(packet)
    fact = lineages[-1].root.fact
    assert isinstance(fact, ActionFact) and fact.behavior_id == "action.attack_object"
    assert fact.target_entity_uuid is None
    assert str(hidden_identity).encode() not in packet
