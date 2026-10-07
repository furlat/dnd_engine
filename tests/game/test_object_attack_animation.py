"""Normal attacks on objects replay their real weapon and impact after reset."""

import random
from uuid import uuid4

import pygame
import pytest

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import AreaReachEvent, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt
from game.animation import ObjectContact, projectile_contact, sample_cast
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import animation_draw_commands, load_animation_media, load_attack_media
from game.attack import BoundAttack, bind_attack, sample_attack
from game.choreography import bind_choreography
from game.combat import bind_cast
from game.feedback import choreography_feedback, sample_feedback
from dnd.player.facts import AreaReachFact, AttackFact, ObjectDamageFact, ObjectDestroyedFact, SpellFact
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_initialization, reduce_lineage
from dnd.player.capture import capture_interval, capture_lineage, reduce_interval
from game.projection import Camera
from dnd.player.recorded import RecordedSequence
from tests.game.object_attack_scenarios import object_attack_history
from tests.game.prop_destruction_scenarios import prop_destruction_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def _object_attack_record(mode, roll):
    random_state = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=(3, 3), faction="heroes"))
        equipment = [(build_authored_item("weapon.longbow", actor.uuid), WeaponSlot.RANGED_MAIN)]
        if mode != "unarmed":
            equipment.append((build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN))
        actor.install_initial_items(tuple(equipment))
        actor.equipment.activate_weapon_slot(WeaponSlot.RANGED_MAIN)
        actor.compose_entity()
        setup_standard_actions(actor)
        if mode == "fire-bolt":
            register_spell(actor, FireBolt, caster_level=1)
        game.deploy_entity(actor, actor.position)
        obj = build_authored_item("environment.blocker.crate", actor.uuid)
        obj.place_on_grid((6, 3) if mode in ("ranged", "fire-bolt") else (4, 3))
        encounter = Encounter(name="Object attack playback", source_entity_uuid=actor.uuid)
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(15):
            encounter.start_encounter()
        encounter.start_turn()
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Attacker with bow", start_cursor=0, end_cursor=cursor,
            observer_uuid=actor.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        assert before.actors[actor.uuid].active_weapon_set is WeaponSet.RANGED
        slot = WeaponSlot.RANGED_MAIN if mode == "ranged" else WeaponSlot.MELEE_MAIN
        choices = [(row, target) for row in get_available_actions(actor).all_actions
                   if (row.behavior_id == "spell.fire_bolt" if mode == "fire-bolt" else
                       row.behavior_id == "action.attack" and row.weapon_slot == slot.value)
                   for target in row.valid_targets if target.target_uuid == obj.uuid]
        assert choices
        assert choices[0][1].target_kind == "object"
        with fixed_dice_faces(roll, 4, 4):
            event = execute_available_action(actor, *choices[0])
        assert isinstance(event, (AttackEvent, SpellEvent)) and not event.canceled
        native = RecordedSequence(initialization=initial,
            lineages=(capture_lineage(event, observer_uuid=actor.uuid),))
        return native.model_dump_json(), actor.uuid, obj.uuid
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)


@pytest.mark.parametrize("mode,stance,profile,clip", [
    ("melee", WeaponSet.MELEE, "melee-main", "Attack1"),
    ("ranged", WeaponSet.RANGED, "ranged", "Attack3"),
    ("unarmed", WeaponSet.NONE, "unarmed", "Attack2"),
])
@pytest.mark.parametrize("roll,outcome", [(1, AttackOutcome.CRIT_MISS), (15, AttackOutcome.HIT)])
def test_saved_normal_object_attack_selects_weapon_and_impact_without_actor_recipient(
    data, mode, stance, profile, clip, roll, outcome,
):
    payload, actor_uuid, object_uuid = _object_attack_record(mode, roll)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0

    native = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    before, (lineage,) = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    root = lineage.root.fact
    assert isinstance(root, AttackFact)
    assert root.target_kind == "object" and root.target_entity_uuid == object_uuid
    assert root.attack_outcome is outcome
    assert object_uuid not in before.actors
    bound = bind_attack(before, lineage, data)
    assert bound is not None
    timeline = bound.timeline
    assert isinstance(timeline.target, ObjectContact)
    assert (timeline.profile_id, timeline.clip) == (profile, clip)
    assert timeline.target.grid == ((6., 3.) if mode == "ranged" else (4., 3.))
    assert bound.after.actors[actor_uuid].visual_loadout.active_weapon_set is stance
    weapons = {layer.category for layer in bound.appearances[str(actor_uuid)] if layer.slot == "weapon"}
    assert bool(weapons) is (mode != "unarmed")
    previous_weapons = {layer.category for layer in resolve_player_layers(data, before.actors[actor_uuid],
        rig_id=timeline.source.rig_id) if layer.slot == "weapon"}
    assert previous_weapons  # Every case begins with the visible, actually equipped bow.
    if mode == "melee":
        assert weapons.isdisjoint(previous_weapons)
    if mode == "ranged":
        assert weapons == previous_weapons
        assert timeline.projectile is not None
        assert timeline.projectile.start_ms < timeline.contact_ms
    else:
        assert timeline.projectile is None
    at_impact = sample_attack(timeline, timeline.contact_ms)
    assert len(at_impact.bodies) == 1 and not at_impact.vitals
    group = bind_choreography(before, lineage, data)
    assert not group.gaps
    assert not group.body_actions
    assert not group.strips  # No creature blood for a prop recipient.
    tracks = choreography_feedback(group, data, 0)
    if outcome is AttackOutcome.HIT:
        damage, = (node.fact for node in lineage.events if isinstance(node.fact, ObjectDamageFact))
        assert any(number.value == damage.applied_damage for number in at_impact.numbers)
        flashes = [row for row in group.world_transitions if row.field == "hit_flash"]
        assert len(flashes) == 1 and flashes[0].start_ms == pytest.approx(timeline.contact_ms)
        assert any((number := sample_feedback(track, timeline.contact_ms)) is not None
                   and number.value == damage.applied_damage for track in tracks)
    else:
        assert not any(isinstance(node.fact, ObjectDamageFact) for node in lineage.events)
        assert any(number.kind == "badge" for number in at_impact.numbers)
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        assert load_attack_media(timeline, bound.appearances)
    finally:
        pygame.quit()
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("roll,outcome", [(1, AttackOutcome.CRIT_MISS), (15, AttackOutcome.HIT)])
def test_fire_bolt_object_uses_the_cast_projectile_and_received_physical_contact(data, roll, outcome):
    payload, actor_uuid, object_uuid = _object_attack_record("fire-bolt", roll)
    native = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    before, (lineage,) = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    fact = lineage.root.fact
    assert isinstance(fact, SpellFact) and fact.target_kind == "object"
    assert fact.attack_outcome is outcome and fact.target_entity_uuid == object_uuid
    bound = bind_cast(before, lineage, data)
    application, = bound.timeline.applications
    contact = application.source.target
    assert isinstance(contact, ObjectContact) and contact.grid == (6., 3.)
    placement = before.objects[object_uuid].placement
    assert contact.elevation_steps == (placement.base_height_steps + placement.top_height_steps) / 2
    assert set(bound.appearances) == {str(actor_uuid)}
    group = bind_choreography(before, lineage, data)
    assert not group.gaps
    assert len(group.nodes) == 1
    assert not group.strips
    impact = sample_cast(bound.timeline, application.travel_end_ms)
    assert len(impact.bodies) == 1 and not impact.vitals
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        media = load_animation_media(bound.timeline, bound.appearances)
        for quadrant in range(4):
            commands = animation_draw_commands(bound.timeline, impact, media, Camera(quadrant=quadrant))
            assert commands
            for sample in impact.projectiles:
                if sample.phase == "impact":
                    grid, height = projectile_contact(bound.timeline, sample, quadrant=quadrant)
                    assert grid == pytest.approx(contact.grid)
                    assert height == pytest.approx(contact.elevation_steps)
        if outcome is AttackOutcome.HIT:
            damage, = (node.fact for node in lineage.events if isinstance(node.fact, ObjectDamageFact))
            assert any(number.value == damage.applied_damage for number in impact.numbers)
            flash, = (row for row in group.world_transitions if row.field == "hit_flash")
            assert flash.start_ms == pytest.approx(application.travel_end_ms)
    finally:
        pygame.quit()
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


def test_breach_packet_discloses_only_received_stage_dependencies():
    history = object_attack_history(program="fireball-breach")
    hidden_dependencies = 0
    for native in history.views.values():
        sequence = project_sequence(native)
        for recorded, public in zip(native.lineages, sequence.lineages, strict=True):
            disclosed = {node.lineage_uuid for node in public.events if node.fact is not None}
            original = {event.lineage_uuid: event for event in recorded.events
                        if isinstance(event, AreaReachEvent)}
            for node in public.events:
                fact = node.fact
                if not isinstance(fact, AreaReachFact):
                    continue
                prerequisites = original[node.lineage_uuid].prerequisite_destruction_lineages
                hidden_dependencies += sum(identity not in disclosed for identity in prerequisites)
                assert fact.prerequisite_destruction_lineages == tuple(
                    identity for identity in prerequisites if identity in disclosed)
                assert fact.previous_reach_lineage_uuid is None or fact.previous_reach_lineage_uuid in disclosed
    assert hidden_dependencies > 0  # One observer cannot perceive the first door breaking.


def test_lethal_object_attack_keeps_intact_contact_until_the_recorded_break(data):
    captured = prop_destruction_history(item_id="environment.furniture.bookshelf")
    payload = captured.views["attacker"].model_dump_json()
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    native = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    sequence = project_sequence(native)
    before = reduce_initialization(sequence.initialization)
    witnessed = 0
    for lineage in sequence.lineages:
        after = reduce_lineage(before, lineage)
        destroyed = [node.fact for node in lineage.events if isinstance(node.fact, ObjectDestroyedFact)]
        if destroyed:
            destruction, = destroyed
            intact = before.objects[destruction.object_uuid].placement
            wreck = after.objects[destruction.object_uuid].placement
            assert intact.top_height_steps > wreck.top_height_steps
            direct = bind_attack(before, lineage, data)
            assert direct is not None and isinstance(direct.timeline.target, ObjectContact)
            expected_height = (intact.base_height_steps + intact.top_height_steps) / 2
            assert direct.timeline.target.elevation_steps == expected_height
            group = bind_choreography(before, lineage, data)
            assert not group.gaps
            attack, = group.nodes
            assert isinstance(attack.bound, BoundAttack)
            assert attack.bound.timeline.target == direct.timeline.target
            assert group.after.objects[destruction.object_uuid].placement == wreck
            witnessed += 1
        before = after
    assert witnessed == 1
