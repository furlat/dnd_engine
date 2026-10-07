"""Native real-item light ownership survives replay, exposure and current poses."""

from dataclasses import replace
from types import MappingProxyType

import pygame
import pytest

from dnd.core.events import EventType
from game.animation import BodySample
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.choreography import bind_choreography
from game.combat import actor_contact
from game.item_attachment_lifetime import item_attachment_members, register_item_attachment_starts
from game.item_draw import item_ground_commands
from game.maintained_media import maintained_media_frame
from dnd.player.facts import ItemEffectChangeFact
from dnd.player.reduction import reduce_lineage
from game.projection import Camera
from tests.game.continual_flame_scenarios import continual_flame_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.fixture(scope="module")
def history():
    return continual_flame_history()


def replay(history, data, role):
    state, roots = player_history(history, role=role)
    starts, clock, rows = {}, 0., []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        starts = register_item_attachment_starts(starts, state, data,
            absolute_start_ms=clock, lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        clock += group.complete_ms + 50
        rows.append((state, starts, clock, root))
    return rows


@pytest.mark.parametrize("observer", ("caster", "recipient"))
def test_real_item_identity_and_birth_clock_survive_carry_cover_drop_loot_suppression(data, history, observer):
    rows = replay(history, data, observer)
    starts = rows[-1][1]
    assert len(starts) == 2
    assert all(start.applied_ms is not None and start.source_cursor is not None for start in starts.values())
    births = {event.fact.effect_uuid for _, _, _, root in rows for event in root.events
        if isinstance(event.fact, ItemEffectChangeFact) and event.fact.event_type is EventType.CONDITION_APPLICATION}
    assert births == set(starts)
    carried = {}
    saw_suppression = saw_covered = False
    for state, retained, _, _ in rows:
        assert state.senses is not None
        assert all(effect.content_ref.content_id != 'spell.continual_flame'
            for effect in state.senses.spatial_effects.values())
        for owner, start in retained.items():
            assert start.applied_ms == starts[owner].applied_ms
            if start.source_cursor is not None:
                assert start.source_cursor == starts[owner].source_cursor
        for actor in state.actors.values():
            for item in actor.visual_loadout.layers:
                for effect in item.item_effects:
                    if effect.effect_uuid in starts:
                        carried.setdefault(effect.effect_uuid, set()).add(actor.uuid)
                        saw_suppression |= bool(effect.suppression_provider_uuids)
            equipped = {item.item_uuid for item in actor.visual_loadout.layers}
            saw_covered |= any(item.item_effects and item.item_uuid not in equipped
                for item in actor.controlled_items or ())
    assert any(len(carriers) == 2 for carriers in carried.values())
    assert saw_suppression
    assert saw_covered
    assert not item_attachment_members(rows[-1][0], data)


def test_floor_flame_uses_real_item_pixels_and_cold_acquisition_has_no_application(data, history):
    rows = replay(history, data, "caster")
    state, starts, clock, _ = next(row for row in rows if any(obj.item.item_effects for obj in row[0].objects.values()))
    obj = next(obj for obj in state.objects.values() if obj.item.item_effects)
    effect, = obj.item.item_effects
    cold = register_item_attachment_starts({}, state, data, absolute_start_ms=clock)
    assert cold[effect.effect_uuid].applied_ms is None
    binding = data.item_attachments[effect.behavior_id]
    for layer in binding.layers:
        sampled = maintained_media_frame(data, binding, layer, clock, cold[effect.effect_uuid].applied_ms)
        assert sampled is not None and sampled[0] == layer.assetId
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant)
        plain = item_ground_commands(obj, camera)[-1]
        flame = item_ground_commands(obj, camera, data=data, time_ms=clock + 1800, starts=starts)[-1]
        assert flame.owner == str(obj.item.item_uuid)
        assert flame.surface.get_bounding_rect().height > plain.surface.get_bounding_rect().height
        suppressed = replace(obj, item=replace(obj.item,
            suppression_provider_uuids=(obj.item.item_uuid,)))
        clear = item_ground_commands(suppressed, camera, data=data, time_ms=clock, starts=starts)[-1]
        assert pygame.image.tobytes(clear.surface, "RGBA") == pygame.image.tobytes(plain.surface, "RGBA")
        assert clear.destination == plain.destination


@pytest.mark.parametrize("clip,frame", (("Idle", 0), ("Run", 7), ("Attack5", 7), ("TakeDamage", 6), ("Die", 12)))
def test_equipped_flame_follows_current_item_layer_and_skips_hidden_or_suppressed_gear(data, history, clip, frame):
    state, starts, clock, _ = next(row for row in replay(history, data, "caster")
        if any(item.item_effects and not item.item_effects[0].suppression_provider_uuids
               for actor in row[0].actors.values() for item in actor.visual_loadout.layers))
    actor = next(actor for actor in state.actors.values() if any(item.item_effects for item in actor.visual_loadout.layers))
    contact = actor_contact(state, actor, data, "S")
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    gear = tuple(layer for layer in layers if layer.item_effects)
    assert gear
    media = load_actor_media(data, ((contact, layers, (clip,)),), all_facings=True)
    plain_data = replace(data, item_attachments=MappingProxyType({}))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant)
        body = BodySample(contact.actor_uuid, clip, frame, "S")
        def draw(selected_data, selected_layers=layers, selected_body=body):
            return next(row for row in actor_draw_commands(selected_data, selected_body, contact,
                selected_layers, media, camera, item_starts=starts, presentation_ms=clock + 1800)
                if row.role == "actor")
        plain, flame = draw(plain_data), draw(data)
        assert (flame.destination, pygame.image.tobytes(flame.surface, "RGBA")) != (
            plain.destination, pygame.image.tobytes(plain.surface, "RGBA"))
        suppressed = tuple(replace(layer, suppression_provider_uuids=(actor.uuid,))
            if layer.item_effects else layer for layer in layers)
        clear = draw(data, suppressed)
        assert clear.destination == plain.destination
        assert pygame.image.tobytes(clear.surface, "RGBA") == pygame.image.tobytes(plain.surface, "RGBA")
        hidden_body = replace(body, hidden_slots=tuple(layer.slot for layer in gear))
        clear, baseline = draw(data, selected_body=hidden_body), draw(plain_data, selected_body=hidden_body)
        assert clear.destination == baseline.destination
        assert pygame.image.tobytes(clear.surface, "RGBA") == pygame.image.tobytes(baseline.surface, "RGBA")


def test_apply_then_hold_uses_existing_registered_frames(data):
    binding = data.item_attachments["condition.spell.continual_flame"]
    for layer in binding.layers:
        assert maintained_media_frame(data, binding, layer, 0, 0) == (layer.applicationAssetId, 0)
        assert maintained_media_frame(data, binding, layer, 1499, 0) == (layer.applicationAssetId, 47)
        assert maintained_media_frame(data, binding, layer, 1500, 0) == (layer.assetId, 0)
        assert maintained_media_frame(data, binding, layer, 3499, 0) == (layer.assetId, 63)
        assert maintained_media_frame(data, binding, layer, 3500, 0) == (layer.assetId, 0)


def test_hidden_application_is_not_replayed_when_another_observer_first_sees_the_item(data):
    history = continual_flame_history(initially_covered=True)
    rows = replay(history, data, "recipient")
    starts = rows[-1][1]
    assert len(starts) == 2
    hidden_owner, = (owner for owner, start in starts.items() if start.applied_ms is None)
    assert not any(isinstance(event.fact, ItemEffectChangeFact)
        and event.fact.effect_uuid == hidden_owner
        and event.fact.event_type is EventType.CONDITION_APPLICATION
        for _, _, _, root in rows for event in root.events)
    first = next(row for row in rows if hidden_owner in item_attachment_members(row[0], data))
    item, effect = item_attachment_members(first[0], data)[hidden_owner]
    assert item == starts[hidden_owner].item_uuid
    binding = data.item_attachments[effect.behavior_id]
    for layer in binding.layers:
        sample = maintained_media_frame(data, binding, layer, first[2], first[1][hidden_owner].applied_ms)
        assert sample is not None and sample[0] == layer.assetId


def test_owned_covered_item_cast_keeps_exact_target_and_caster_animation_without_world_object(data):
    history = continual_flame_history(initially_covered=True)
    state, roots = player_history(history, role="caster")
    checked = False
    for root in roots:
        fact = root.root.fact
        if fact is not None and fact.kind == "spell" and fact.target_entity_uuid not in state.objects:
            assert any(item.item_uuid == fact.target_entity_uuid
                for item in state.actors[state.observer_uuid].controlled_items or ())
            group = bind_choreography(state, root, data)
            assert not group.gaps
            cast, = group.body_actions
            assert cast.recipe_id == "spell.continual_flame"
            assert cast.event_uuid == root.root.uuid
            assert fact.target_entity_uuid not in group.after.objects
            starts = register_item_attachment_starts({}, state, data,
                absolute_start_ms=100, lineage=root, choreography=group)
            birth, = starts.values()
            assert birth.applied_ms == pytest.approx(100 + cast.effect_ms)
            checked = True
            break
        state = reduce_lineage(state, root)
    assert checked
