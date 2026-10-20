"""Actual sphere END contacts identify their observed zone in detached updates.

Two prepared Wizards summon independent spheres around one enemy. Native turns,
Ram and concentration removal must preserve the emitting zone without assigning
ordinary fire damage to a nearby aura or exposing an unobserved spatial owner.
"""

from dataclasses import replace
import random

import pytest

from dnd.actions import SpellAction
from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.conditions import Blinded
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.entity import Entity
from dnd.monsters.spell_summons import FlamingSphereZone
from dnd.player.application import initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session, create_session, publish_sheets
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from tests.player.test_emitted_update_replica import INITIALIZATION
from tests.player.test_holy_nimbus_attribution import capture, damage_facts
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def sphere_arena():
    previous_random = random.getstate()
    random.seed(6)
    build = replace(prepared_build(CharacterClass.WIZARD, 5),
        scribed_spell_ids=("spell.flaming_sphere",), prepared_spells=(
            PreparedSpellSelection("class.wizard.spellcasting", ("spell.flaming_sphere",)),))
    session = create_session(player_builds=(replace(build, name="First summoner"),
        replace(build, name="Second summoner")), player_positions=((10, 10), (10, 12)),
        enemy_positions=((13, 10), (14, 12)))
    try:
        casters = tuple(session.game.entities[identity] for identity in session.player_uuids)
        enemy = next(actor for actor in session.game.entities.values()
            if casters[0].is_enemy(actor) and actor.position == (13, 10))
        add_modifier(enemy.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name="Survive independent sphere contacts", value=100,
                source_entity_uuid=enemy.uuid))
        session = replace(session, player_uuids=(*session.player_uuids, enemy.uuid))
        session.seats["recipient"] = PlayerAudience((enemy.uuid,), (enemy.uuid,))
        publish_sheets(session)
        yield session, casters, enemy
    finally:
        close_session(session)
        random.setstate(previous_random)


def cast_spheres(session, casters, audiences, catalog):
    """Cast two independent prepared spheres and retain their public births."""
    zones = {}
    births = []
    for caster, position in zip(casters, ((12, 10), (13, 11)), strict=True):
        template, = (action for action in caster.registered_actions
            if isinstance(action, SpellAction) and action.semantic_key == "spell.flaming_sphere")
        variant, = (variant for variant in template.discovery_forms(caster.action_scan(subjective=True))
            if variant.cast_at_level == 2)
        cursor = EventQueue.event_cursor()
        result = caster.perform(template, replace(variant.current_selection(),
            positions=(position,), cast_at_level=2))
        assert result is not None and not result.canceled
        zone, = (zone for zone in get_map().get_spatial_conditions()
            if isinstance(zone, FlamingSphereZone) and zone.source_entity_uuid == caster.uuid)
        zones[caster.uuid] = zone
        births.append(capture(session, audiences, catalog, cursor))
    return zones, births


def sphere_turn_end(session, enemy, audiences, catalog):
    """One real recipient END, capture and detached JSON round trip."""
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 60)):
        assert not enemy.on_turn_end().canceled
    return cursor, capture(session, audiences, catalog, cursor)


@pytest.mark.parametrize("blind_recipient", [False, True])
def test_sphere_end_contact_preserves_exact_zone_and_disclosure(sphere_arena, blind_recipient):
    session, casters, enemy = sphere_arena
    catalog = ui_content_manifest()
    audiences, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
        content_additions=seat_content(audiences[seat])) for seat, initial in initializations.items()}
    if blind_recipient:
        cursor = EventQueue.event_cursor()
        result = enemy.add_condition(Blinded(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
        assert result is not None and not result.canceled
        for seat, update in capture(session, audiences, catalog, cursor).items():
            clients[seat] = reduce_operation(clients[seat], update)
    zones, births = cast_spheres(session, casters, audiences, catalog)
    for updates in births:
        for seat, update in updates.items():
            clients[seat] = reduce_operation(clients[seat], update)
    assert len({zone.uuid for zone in zones.values()}) == 2
    assert len({zone.anchor_uuid for zone in zones.values()}) == 2
    for seat, client in clients.items():
        assert client.senses is not None
        for zone in zones.values():
            if seat == "recipient" and blind_recipient:
                assert zone.uuid not in client.senses.spatial_effects
            else:
                retained = client.senses.spatial_effects[zone.uuid]
                assert retained.content_ref.content_id == "spatial_effect.spell.flaming_sphere.aura"
                assert retained.anchor_entity_uuid == zone.anchor_uuid

    hp = enemy.get_normal_hp()
    cursor, updates = sphere_turn_end(session, enemy, audiences, catalog)
    assert enemy.get_normal_hp() == hp - 8
    native = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == enemy.uuid]
    expected = {caster: zone.uuid for caster, zone in zones.items()}
    assert set(updates) == {"party", "recipient"}
    for seat, update in updates.items():
        facts = damage_facts(update, enemy.uuid)
        assert len(facts) == 2
        assert all(fact.damage_type is DamageType.FIRE and fact.applied_damage == 4 for fact in facts)
        if seat == "recipient" and blind_recipient:
            assert all(fact.source_condition_uuid is None for fact in facts)
        else:
            assert {fact.source_entity_uuid: fact.source_condition_uuid for fact in facts} == expected
            assert all(fact.source_condition_uuid in clients[seat].senses.spatial_effects for fact in facts)
        clients[seat] = reduce_operation(clients[seat], update)
    assert {event.source_entity_uuid: event.source_condition_uuid for event in native} == expected

    # Same caster/type/nearby zones do not attribute ordinary damage to an aura.
    cursor = EventQueue.event_cursor()
    assert enemy.receive_damage(4, DamageType.FIRE, casters[1].uuid) == 4
    for seat, update in capture(session, audiences, catalog, cursor).items():
        fact, = damage_facts(update, enemy.uuid)
        assert fact.source_condition_uuid is None and fact.applied_damage == 4
        clients[seat] = reduce_operation(clients[seat], update)

    # Ram remains an action-owned contact, distinct from the zone's END cadence.
    sphere = Entity.get(zones[casters[1].uuid].anchor_uuid)
    assert sphere is not None
    ram, = (row for row in get_available_actions(sphere).all_actions
        if row.behavior_id == "action.spell.flaming_sphere.ram")
    target, = (target for target in ram.valid_targets if target.target_uuid == enemy.uuid)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 30)):
        result = execute_available_action(sphere, ram, target)
    assert result is not None and not result.canceled
    for seat, update in capture(session, audiences, catalog, cursor).items():
        fact, = damage_facts(update, enemy.uuid)
        assert fact.source_condition_uuid is None and fact.applied_damage == 4
        clients[seat] = reduce_operation(clients[seat], update)

    cursor = EventQueue.event_cursor()
    assert casters[0].remove_condition("Concentrating")
    for seat, update in capture(session, audiences, catalog, cursor).items():
        clients[seat] = reduce_operation(clients[seat], update)
        assert zones[casters[0].uuid].uuid not in clients[seat].senses.spatial_effects
        if seat != "recipient" or not blind_recipient:
            assert zones[casters[1].uuid].uuid in clients[seat].senses.spatial_effects
    assert get_map().get_spatial_condition(zones[casters[0].uuid].uuid) is None
    _, updates = sphere_turn_end(session, enemy, audiences, catalog)
    for seat, update in updates.items():
        fact, = damage_facts(update, enemy.uuid)
        assert fact.applied_damage == 4
        assert fact.source_condition_uuid == (None if seat == "recipient" and blind_recipient
            else zones[casters[1].uuid].uuid)
