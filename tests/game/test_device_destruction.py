"""Observed destruction settles independently of native cleanup and replay."""

from dataclasses import replace
import gzip
from pathlib import Path
from uuid import uuid4

import pygame
import pytest

from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.creature_types import DamageType
from dnd.core.events import (EventPhase, EventQueue, ItemDestructionEvent, SensoryUpdateEvent,
                             SpatialChangeEvent, SpatialChangeType, TakeDamageEvent)
from dnd.core.item_types import ItemIntegrity, ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.device_art import DeviceEmission, device_bank, load_device_art
from game.device_draw import device_draw_command, device_wreck_draw_command
from game.event_record import decode_event, encode_event
from game.playback_frame import sample_playback_frame
from game.player_facts import ObjectDamageFact, ObjectDestroyedFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, capture_lineages
from game.projection import Camera, project_screen
from game.replay import RecordedSequence
from game.scene import load_scene_media, scene_actors
from tests.game.web_scenarios import web_history
from tests.game.device_scenarios import device_history


@pytest.fixture(scope="module")
def recorded():
    return web_history(delivery="cannon")


@pytest.fixture(scope="module")
def legacy_recorded():
    # Actual pre-migration recording from inputs/device-break-cannon/native.json.
    path = Path(__file__).parent / "fixtures/legacy-device-destruction.json.gz"
    return RecordedSequence.model_validate_json(gzip.decompress(path.read_bytes()), context=PASSIVE_EVENT_REPLAY)


@pytest.fixture(scope="module")
def raster():
    pygame.init()
    screen = pygame.display.set_mode((700, 500))
    catalog = load_catalog()
    data = load_animation_data()
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                  for style in (data.number_style, data.badge_style))
    yield screen, catalog, SurfaceCache(catalog), data, fonts
    pygame.quit()


def _destruction(native):
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    for lineage in lineages:
        found = [node.fact for node in lineage.events if isinstance(node.fact, ObjectDestroyedFact)]
        if found:
            assert len(found) == 1
            return state, lineage, found[0]
        state = reduce_lineage(state, lineage)
    pytest.fail("An actually observed native destruction must retain its explicit public fact")


@pytest.mark.parametrize("role", ("caster", "target"))
def test_native_destruction_settles_same_device_body_after_contact_without_retaining_links(recorded, raster, role):
    screen, catalog, cache, data, fonts = raster
    before, lineage, fact = _destruction(recorded.views[role])
    after = reduce_lineage(before, lineage)
    replacement = fact.object_uuid
    assert fact.replacement_uuid is None
    assert set(before.objects) == set(after.objects)
    assert before.objects[replacement].item.integrity is ItemIntegrity.INTACT
    assert after.objects[replacement].item.integrity is ItemIntegrity.DESTROYED
    assert after.objects[replacement].item.item_id == "environment.arcane_machine_gun"
    assert not after.objects[replacement].item.concentration_slots
    assert before.senses is not None and len(before.senses.spatial_effects) == 2
    assert after.senses is not None and not after.senses.spatial_effects
    # Historical aiming can differ from native placement orientation. Keep it
    # when the same body's physical state becomes destroyed.
    facing = "NW"
    group = bind_choreography(before, lineage, data, facings={str(fact.object_uuid): facing})
    destruction, = (row for row in group.world_transitions if row.field == "destruction")
    contact = destruction.destruction
    assert contact is not None and contact.body_uuid == replacement and contact.facing == facing
    gesture, = group.body_actions
    assert destruction.start_ms == gesture.effect_ms
    assert contact.duration_ms == pytest.approx(8 * 1000 / 12)
    assert group.complete_ms >= destruction.start_ms + contact.duration_ms
    rows = {}
    bodies = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})), data, body_rows=rows)
    media = load_choreography_media(group, body_rows=rows)
    cursor = EventQueue.event_cursor()
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(fact.placement.position)

        def render(time, *, idle=False, facings=None):
            frame = sample_playback_frame(after if idle else before, None if idle else after, data,
                time, 3000, camera, facings or {str(fact.object_uuid): facing}, bodies, *fonts,
                choreography=None if idle else group, choreography_media=None if idle else media)
            evidence = draw_frame(screen, frame.displayed, catalog, cache, camera, 3,
                show_grid=False, show_debug=False, mouse_position=None, extra_commands=frame.commands,
                world_transitions=frame.world_transitions, collect_evidence=True)
            assert evidence is not None and evidence.matches
            devices = [row for row in evidence.actual_draws if len(row) > 6 and row[6] in ("device", "device_wreck")]
            tethers = [row for row in evidence.actual_draws if len(row) > 6 and row[6] == "sustained_tether"]
            pixels = pygame.image.tobytes(screen, "RGBA")
            draw_frame(screen, frame.displayed, catalog, cache, camera, 3,
                show_grid=False, show_debug=False, mouse_position=None,
                extra_commands=tuple(row._replace(evidence=()) for row in frame.commands),
                world_transitions=frame.world_transitions)
            assert pygame.image.tobytes(screen, "RGBA") == pixels
            return frame, devices, tethers, pixels

        winding, devices, tethers, wind_pixels = render(destruction.start_ms - .001)
        assert winding.displayed.objects[replacement].item.integrity is ItemIntegrity.INTACT
        assert len(devices) == 1 and devices[0][6] == "device" and len(tethers) > 0
        struck, devices, tethers, strike_pixels = render(destruction.start_ms)
        assert struck.displayed.objects[replacement].item.integrity is ItemIntegrity.DESTROYED
        assert len(devices) == 1 and devices[0][0] == str(replacement)
        assert devices[0][6:10] == ("device_wreck", fact.placement.base_height_steps, facing, 0)
        assert not tethers
        _, devices, _, _ = render(destruction.start_ms + 7 * 1000 / 12 + .001)
        assert len(devices) == 1 and devices[0][9] == 7
        settled, devices, _, settled_pixels = render(group.complete_ms)
        assert settled.complete and settled.facings[str(replacement)] == facing
        assert len(devices) == 1 and devices[0][6:10] == ("device_wreck", fact.placement.base_height_steps, facing, 0)
        assert render(0, idle=True, facings=settled.facings)[3] == settled_pixels
        assert render(destruction.start_ms - .001)[3] == wind_pixels
        assert render(destruction.start_ms)[3] == strike_pixels
    assert EventQueue.event_cursor() == cursor


@pytest.mark.parametrize("identity", ("environment.fireball_cannon", "environment.arcane_machine_gun"))
def test_selected_break_frames_match_idle_and_wreck_for_all_cameras_and_aims(raster, identity):
    art = load_device_art()[identity]
    assert art.destruction is not None
    # Historical pitch metadata remains available, but the authored launch
    # pitch selects the production body and its matching break sequence.
    bank = device_bank(art)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus((5, 7), elevation_steps=2)
        for facing in art.rows:
            emitter = DeviceEmission("device", (5, 7), 2, facing, art, bank)
            live = device_draw_command(emitter, 0, camera)
            first = device_wreck_draw_command("wreck", (5, 7), 2, facing, art, camera,
                elapsed_ms=0, pitch_degrees=bank.degrees)
            final = device_wreck_draw_command("wreck", (5, 7), 2, facing, art, camera,
                elapsed_ms=7 * 1000 / 12 + .001, pitch_degrees=bank.degrees)
            wreck = device_wreck_draw_command("wreck", (5, 7), 2, facing, art, camera)
            assert live.destination == first.destination == final.destination == wreck.destination
            support = project_screen((5, 7), camera, elevation_steps=2)
            assert wreck.destination == tuple(round(support[i] - art.anchor[i] * art.scale * camera.zoom) for i in range(2))
            assert pygame.image.tobytes(live.surface, "RGBA") == pygame.image.tobytes(first.surface, "RGBA")
            assert pygame.image.tobytes(final.surface, "RGBA") == pygame.image.tobytes(wreck.surface, "RGBA")


def test_unknown_replacement_is_redacted_and_legacy_destruction_never_invents_one(legacy_recorded):
    native = legacy_recorded
    root = native.lineages[-1]
    destroyed, = (event for event in root.events if isinstance(event, ItemLocationStateEvent)
                  and event.location is ItemLocation.DESTROYED)
    unknown = uuid4()
    changed = destroyed.model_copy(update={"replacement_item_uuid": unknown})
    altered = replace(root, events=tuple(changed if event.uuid == destroyed.uuid else event for event in root.events))
    wire = encode_player_sequence(project_sequence(native.model_copy(update={"lineages": (*native.lineages[:-1], altered)})))
    assert str(unknown).encode() not in wire
    _, lineages = decode_player_sequence(wire)
    fact, = (node.fact for node in lineages[-1].events if isinstance(node.fact, ObjectDestroyedFact))
    assert fact.replacement_uuid is None
    old_wire = encode_event(destroyed)
    old_wire.pop("replacement_item_uuid")
    restored = decode_event(old_wire)
    assert isinstance(restored, ItemLocationStateEvent) and restored.replacement_item_uuid is None


@pytest.mark.parametrize("family,outcome", (("device", None), ("door", "clear")))
def test_archived_replacement_and_same_identity_settled_bodies_have_identical_pixels(raster, family, outcome):
    path = Path(__file__).parent / f"fixtures/legacy-{family}-destruction.json.gz"
    archived = RecordedSequence.model_validate_json(gzip.decompress(path.read_bytes()), context=PASSIVE_EVENT_REPLAY)
    before, root, fact = _destruction(archived)
    assert fact.replacement_uuid is not None and fact.replacement_uuid != fact.object_uuid
    after = reduce_lineage(before, root)
    assert fact.object_uuid not in after.objects and fact.replacement_uuid in after.objects
    group = bind_choreography(before, root, raster[3])
    transition, = (row for row in group.world_transitions if row.field == "destruction")
    assert transition.destruction is not None and transition.destruction.body_uuid == fact.replacement_uuid
    assert not group.gaps
    wreck = after.objects[fact.replacement_uuid]
    persistent = replace(wreck, placement=wreck.placement.model_copy(update={"object_uuid": fact.object_uuid}),
        item=replace(wreck.item, item_uuid=fact.object_uuid, item_id=fact.item_id,
                     integrity=ItemIntegrity.DESTROYED, destruction_outcome=outcome))
    assert after.senses is not None
    contact = after.senses.objects[fact.replacement_uuid]
    same_identity = replace(after,
        objects={**{key: value for key, value in after.objects.items() if key != fact.replacement_uuid},
                 fact.object_uuid: persistent},
        senses=replace(after.senses, objects={
            **{key: value for key, value in after.senses.objects.items() if key != fact.replacement_uuid},
            fact.object_uuid: contact}))
    screen, catalog, cache, _, _ = raster
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(fact.placement.position)
        images = []
        for state in (after, same_identity):
            draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                       show_debug=False, mouse_position=None)
            images.append(pygame.image.tobytes(screen, "RGBA"))
        assert images[0] == images[1], (family, quadrant)


def test_removal_and_new_object_without_disclosed_destruction_have_no_break_transition(recorded, raster):
    before, root, fact = _destruction(recorded.views["target"])
    _, _, _, data, _ = raster
    # A public stream can retain ordinary object removal/placement while the
    # semantic cause is undisclosed. Those world updates alone grant no break.
    hidden = replace(root, events=tuple(replace(node, fact=None)
        if isinstance(node.fact, ObjectDestroyedFact) else node for node in root.events))
    group = bind_choreography(before, hidden, data)
    assert group.after.objects[fact.object_uuid].item.integrity is ItemIntegrity.DESTROYED
    assert not any(row.field == "destruction" for row in group.world_transitions)


def test_unseen_old_device_does_not_gain_a_break_animation_from_late_wreck_sight(legacy_recorded, raster):
    native = legacy_recorded
    _, _, original = _destruction(native)

    def without_old_contact(event):
        if isinstance(event, SensoryUpdateEvent):
            return event.model_copy(update={"object_contacts_changed": {
                identity: contact for identity, contact in event.object_contacts_changed.items()
                if identity != original.object_uuid}})
        return event

    initialization = replace(native.initialization, admitted=tuple(
        (index, without_old_contact(event)) for index, event in native.initialization.admitted))
    roots = tuple(replace(root, events=tuple(without_old_contact(event) for event in root.events)) for root in native.lineages)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(native.model_copy(update={
        "initialization": initialization, "lineages": roots}))))
    assert original.object_uuid not in state.objects
    for root in lineages:
        assert not any(isinstance(node.fact, (ObjectDestroyedFact, ObjectDamageFact)) for node in root.events)
        state = reduce_lineage(state, root)
    assert original.replacement_uuid in state.objects
    screen, catalog, cache, _, _ = raster
    camera = Camera(viewport=screen.get_size()).with_focus(original.placement.position)
    evidence = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
        show_debug=False, mouse_position=None, collect_evidence=True)
    assert evidence is not None
    wreck, = (row for row in evidence.actual_draws if len(row) > 6 and row[6] == "device_wreck")
    assert wreck[0] == str(original.replacement_uuid) and wreck[9] == 0


def test_legacy_remembered_device_hidden_before_removal_does_not_borrow_lineage_entry_sight():
    # The actual old Web cleanup has sensory children before object removal;
    # today's dedicated destruction event starts before those children.
    path = Path(__file__).parent / "fixtures/legacy-web-destruction.json.gz"
    native = RecordedSequence.model_validate_json(gzip.decompress(path.read_bytes()), context=PASSIVE_EVENT_REPLAY)
    before, _, original = _destruction(native)
    assert before.senses is not None and original.object_uuid in before.senses.objects
    root = native.lineages[-1]
    removed, = (event for event in root.events if isinstance(event, SpatialChangeEvent)
                and event.change_type is SpatialChangeType.OBJECT_REMOVED
                and event.object_uuid == original.object_uuid)
    removal_start = min(row.source_index for row in root.objective_rows if row.lineage_uuid == removed.lineage_uuid)
    indexes = {row.event_uuid: row.source_index for row in root.objective_rows}
    prior = next(event for event in root.events if isinstance(event, SensoryUpdateEvent)
                 and event.observer_uuid == native.initialization.observer_uuid
                 and indexes[event.uuid] < removal_start)
    hidden = prior.model_copy(update={"object_contacts_removed": {*prior.object_contacts_removed, original.object_uuid},
        "object_contacts_changed": {identity: contact for identity, contact in prior.object_contacts_changed.items()
                                    if identity != original.object_uuid}})
    altered = replace(root, events=tuple(hidden if event.uuid == prior.uuid else event for event in root.events))
    _, lineages = decode_player_sequence(encode_player_sequence(project_sequence(native.model_copy(update={
        "lineages": (*native.lineages[:-1], altered)}))))
    assert not any(isinstance(node.fact, (ObjectDestroyedFact, ObjectDamageFact)) for node in lineages[-1].events)


def test_new_destruction_keeps_witnessed_entry_when_its_sensory_children_lose_contact(recorded):
    native = recorded.views["target"]
    _, _, original = _destruction(native)
    root = native.lineages[-1]
    destroyed, = (event for event in root.events if isinstance(event, ItemDestructionEvent)
                  and event.item_uuid == original.object_uuid)
    entry = min(row.source_index for row in root.objective_rows if row.lineage_uuid == destroyed.lineage_uuid)
    indexes = {row.event_uuid: row.source_index for row in root.objective_rows}
    observed_children = tuple(event for event in root.events if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == native.initialization.observer_uuid and indexes[event.uuid] > entry)
    assert observed_children, "The real cleanup must publish sensory changes after destruction entry"
    replacements = {event.uuid: event.model_copy(update={
        "object_contacts_removed": {*event.object_contacts_removed, original.object_uuid},
        "object_contacts_changed": {identity: contact for identity, contact in event.object_contacts_changed.items()
                                    if identity != original.object_uuid}}) for event in observed_children}
    altered = replace(root, events=tuple(replacements.get(event.uuid, event) for event in root.events))
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(native.model_copy(update={
        "lineages": (*native.lineages[:-1], altered)}))))
    breaks = [node.fact for node in lineages[-1].events if isinstance(node.fact, ObjectDestroyedFact)]
    assert len(breaks) == 1 and breaks[0].object_uuid == original.object_uuid
    assert any(isinstance(node.fact, ObjectDamageFact) for node in lineages[-1].events)
    for lineage in lineages:
        state = reduce_lineage(state, lineage)
    assert state.senses is not None and original.object_uuid not in state.senses.objects


def test_native_terminal_item_has_one_break_fact_and_no_retained_body():
    reset_engine_runtime()
    try:
        battlefield_id = "battlefield.open_floor_bright"
        build_battlefield(battlefield_id)
        game = Game()
        witness = Entity.create(uuid4(), "Witness", config=EntityConfig(position=(2, 2)))
        witness.compose_entity()
        game.deploy_entity(witness, (2, 2))
        item = BaseItem(source_entity_uuid=witness.uuid, item_id="test.terminal_crate", name="Terminal crate",
            is_targetable=True, health=BaseItem.create_item_health(witness.uuid, 2))
        item.place_on_grid((3, 2))
        start = EventQueue.event_cursor()
        initialization = capture_interval(name="init", start_cursor=0, end_cursor=start,
            observer_uuid=witness.uuid, battlefield_id=battlefield_id)
        item.receive_damage(2, DamageType.BLUDGEONING, witness.uuid)
        roots = tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase is EventPhase.COMPLETION)
        native = RecordedSequence(initialization=initialization, lineages=capture_lineages(roots,
            observer_uuid=witness.uuid, known_actor_uuids=frozenset((witness.uuid,))))
        restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(restored)))
        assert item.uuid in state.objects
        facts = [node.fact for lineage in lineages for node in lineage.events
                 if isinstance(node.fact, ObjectDestroyedFact)]
        assert len(facts) == 1 and facts[0].object_uuid == item.uuid and facts[0].replacement_uuid is None
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
        assert item.uuid not in state.objects
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize("program", ("break-cannon", "break-projector"))
def test_real_sleep_then_nonlethal_and_lethal_attacks_bind_only_the_actual_break(raster, program):
    captured = device_history(program=program)
    _, _, _, data, _ = raster
    for native in captured.views.values():
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        breaks = []
        for root in roots:
            group = bind_choreography(state, root, data)
            changes = [row for row in group.world_transitions if row.field == "destruction"]
            facts = [node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
            assert len(changes) == len(facts)
            if changes:
                gesture, = group.body_actions
                assert changes[0].start_ms == gesture.effect_ms
                assert not group.gaps
                breaks.extend(changes)
            state = reduce_lineage(state, root)
        assert len(breaks) == 1, "Sleep and a nonlethal hit do not break the body"
        contact = breaks[0].destruction
        assert contact is not None and contact.body_uuid in state.objects
        assert any(condition.behavior_id == "condition.spell.sleep"
                   for actor in state.actors.values() for condition in actor.conditions), "Device destruction must not end Sleep"


@pytest.mark.parametrize("program", ("break-cannon", "break-projector", "break-fireball"))
def test_real_item_hits_flash_at_contact_then_restore_approved_body_pixels(raster, program):
    screen, catalog, cache, data, fonts = raster
    captured = device_history(program=program)
    unflashed = replace(data, damage_context=data.damage_context.model_copy(update={"flashEnabled": False}))
    cursor = EventQueue.event_cursor()
    for native in captured.views.values():
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        hits = []
        for root in roots:
            facts = [node.fact for node in root.events if isinstance(node.fact, ObjectDamageFact)]
            if not facts:
                state = reduce_lineage(state, root)
                continue
            fact, = facts
            hits.append((fact.applied_damage, fact.resulting_hp))
            group = bind_choreography(state, root, data)
            plain = bind_choreography(state, root, unflashed)
            gesture, = group.body_actions
            flash, = (row for row in group.world_transitions if row.hit_flash is not None)
            assert flash.start_ms == gesture.effect_ms
            assert flash.hit_flash is not None
            rows = {}
            bodies = load_scene_media((*scene_actors(state, data, {}), *scene_actors(group.after, data, {})),
                                      data, body_rows=rows)
            media = load_choreography_media(group, body_rows=rows)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((4, 5))

                def render(bound, time):
                    frame = sample_playback_frame(state, bound.after, data, time, 3000, camera,
                        {}, bodies, *fonts, choreography=bound, choreography_media=media)
                    draw_frame(screen, frame.displayed, catalog, cache, camera, 3,
                        show_grid=False, show_debug=False, mouse_position=None,
                        extra_commands=frame.commands, world_transitions=frame.world_transitions)
                    return pygame.image.tobytes(screen, "RGBA")

                for offset, differs in ((-.001, False), (50, True), (flash.hit_flash.durationMs + 1, False)):
                    at = flash.start_ms + offset
                    assert (render(group, at) != render(plain, at)) is differs
                assert render(group, group.complete_ms) == render(plain, group.complete_ms)
                # Seeking back replays the flash, without mutating source sprites or native state.
                assert render(group, flash.start_ms + 50) != render(plain, flash.start_ms + 50)
            state = group.after
        assert hits == [(4, 8), (8, 0)]
    assert EventQueue.event_cursor() == cursor


@pytest.mark.parametrize("canceled", (False, True))
def test_zero_or_canceled_item_damage_has_no_flash(recorded, raster, canceled):
    native = recorded.views["caster"]
    _, _, destroyed = _destruction(native)
    roots = tuple(replace(root, events=tuple(
        event.model_copy(update={"final_damage": 0, "canceled": canceled})
        if isinstance(event, TakeDamageEvent) and event.target_entity_uuid == destroyed.object_uuid
        else event for event in root.events)) for root in native.lineages)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(
        native.model_copy(update={"lineages": roots}))))
    for root in lineages:
        group = bind_choreography(state, root, raster[3])
        assert not any(row.hit_flash is not None for row in group.world_transitions)
        state = group.after
