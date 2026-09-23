"""Web's observed lifetime replays without a live game or asset executors."""

import pytest

from dnd.actions import SpellEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY, BaseObject
from dnd.core.events import EventPhase, EventQueue, SavingThrowEvent, SkillCheckEvent, TakeDamageEvent
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from game.player_facts import ActionFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.web_scenarios import web_history


@pytest.fixture(scope="module", params=("mage", "cannon"))
def web_capture(request):
    return request.param, web_history(delivery=request.param)


def test_web_gallery_actions_resolve_real_saves_escape_and_native_cleanup(web_capture) -> None:
    delivery, captured = web_capture
    native = captured.views["caster"]
    assert set(captured.views) == {"caster", "target"}
    spells = [root for root in native.lineages if isinstance(root.root, SpellEvent)]
    assert len(spells) == (2 if delivery == "cannon" else 1)
    first = spells[0]
    assert isinstance(first.root, SpellEvent)
    assert first.root.behavior_id == "spell.web" and first.root.aoe_position == (9, 5)
    assert first.root.source_position == (3, 5)
    assert first.root.cast_origin == ("source_item" if delivery == "cannon" else "actor")
    assert (first.root.source_item_uuid is None) == (delivery == "mage")
    assert first.root.resolved_area_positions is not None and len(first.root.resolved_area_positions) == 16
    saves = {event.target_entity_name: event for event in first.events if isinstance(event, SavingThrowEvent)}
    assert saves["Target"].result is False and saves["Second"].result is True
    assert all(event.dice_roll is not None for event in saves.values())
    escape = next(root for root in native.lineages if root.root.name == "Escape Web")
    checks = [event for event in escape.events if isinstance(event, SkillCheckEvent)]
    assert len(checks) == 1 and checks[0].result is True and checks[0].dice_roll is not None
    assert native.lineages[-1].root.name == ("Attack Object" if delivery == "cannon" else "Drop Concentration")
    if delivery == "cannon":
        second = spells[1].root
        assert isinstance(second, SpellEvent) and second.aoe_position == (13, 5)
        assert second.source_item_uuid == first.root.source_item_uuid
        damage = [event for event in native.lineages[-1].events if isinstance(event, TakeDamageEvent)]
        assert len(damage) == 1 and damage[0].target_entity_uuid == first.root.source_item_uuid
        assert damage[0].resulting_hp == 0


@pytest.mark.parametrize("role", ("caster", "target"))
def test_web_saved_public_events_retain_saves_zones_slots_and_cleanup(web_capture, role) -> None:
    delivery, captured = web_capture
    original = captured.views[role]
    restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(restored))
    state, roots = decode_player_sequence(payload)
    initial_hp = {actor.uuid: actor.normal_hp for actor in state.actors.values()}
    casts_seen = 0
    first_slot = None
    device_uuid = None
    escaped = False
    for root in roots:
        nodes = {event.lineage_uuid for event in root.events}
        assert all(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL) for event in root.events)
        assert all(child in nodes for event in root.events for child in event.children_lineages)
        assert not root.root.canceled
        state = reduce_lineage(state, root)
        actors = {actor.name: actor for actor in state.actors.values()}
        assert state.senses is not None
        fact = root.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == "spell.web":
            casts_seen += 1
            zones = state.senses.spatial_effects
            assert len(zones) == casts_seen
            assert all(effect.content_ref.content_id == "spatial_effect.spell.web"
                       and effect.trap_state is None for effect in zones.values())
            assert any(condition.behavior_id == "condition.restrained" for condition in actors["Target"].conditions)
            assert not actors["Second"].conditions
            if delivery == "cannon":
                device_uuid = fact.source_item_uuid
                assert device_uuid is not None and not actors["Caster"].conditions
                device = state.objects[device_uuid].item
                assert device.current_hit_points == device.maximum_hit_points == 8
                assert device.concentration_capacity == 2 and len(device.concentration_slots) == casts_seen
                ids = {slot.slot_uuid for slot in device.concentration_slots}
                assert len(ids) == casts_seen
                assert {slot.spell_id for slot in device.concentration_slots} == {"spell.web"}
                if first_slot is None:
                    first_slot = next(iter(ids))
                else:
                    assert first_slot in ids
                assert {effect.concentration_slot_uuid for effect in zones.values()} == ids
                assert all(effect.sustainer_item_uuid == device_uuid for effect in zones.values())
                assert {effect.anchor_position for effect in zones.values()} == ({(9, 5)} if casts_seen == 1 else {(9, 5), (13, 5)})
            else:
                assert any(condition.behavior_id == "condition.concentrating" for condition in actors["Caster"].conditions)
                assert all(effect.sustainer_item_uuid is None for effect in zones.values())
        elif isinstance(fact, ActionFact) and fact.name == "Escape Web":
            escaped = True
            assert not actors["Target"].conditions
            assert len(state.senses.spatial_effects) == 1, "Escape releases the creature, not the persistent Web"
    assert escaped and casts_seen == (2 if delivery == "cannon" else 1)
    assert state.senses is not None and not state.senses.spatial_effects
    assert all(not actor.conditions for actor in state.actors.values())
    assert {actor.uuid: actor.normal_hp for actor in state.actors.values()} == initial_hp
    final = {actor.name: actor for actor in state.actors.values()}
    assert final["Target"].last_visual_position == (11, 5)
    assert final["Second"].last_visual_position == (8, 7)
    if device_uuid is not None:
        assert state.objects[device_uuid].item.integrity is ItemIntegrity.DESTROYED
        assert not state.objects[device_uuid].item.concentration_slots
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities() and not BaseObject._registry
