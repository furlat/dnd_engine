"""Native summon lifetimes survive public replay; Fey bodies keep source shadows."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.creature_types import DamageType
from dnd.core.dice import DiceRoll, fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.summoning import ConjureAnimals, ConjureFey, ConjureFiend
from dnd.summoning.system import bind_summoning
from dnd.types.summoning import SummonManifestation
from game.animation import ActorContact, BodySample
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from dnd.conditions import Prone
from game.animation_types import RigLayer
from game.choreography import bind_choreography, sample_choreography
from game.body_presentation import sample_body_presentation
from game.player_facts import ActionFact, DamageResultFact, FactionFact, SpatialFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, observe_actors, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera, TILE_WIDTH
from game.replay import ObserverCapture, RecordedSequence, capture_history
from game.scene import scene_actors
from tests.game.visibility_scenarios import visibility_history


def summon_history(ending, *, visibility="visible", family="animals", death_saves=False, prone_before_departure=False):
    reset_engine_runtime()
    if not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    family = "fey" if ending == "control_loss" else family
    spell = {"animals": ConjureAnimals, "fey": ConjureFey, "fiend": ConjureFiend}[family]
    encounter = Encounter(source_entity_uuid=uuid4(), name="Summon presentation")
    try:
        actors = []
        for name, position, faction in (("Caster", (2, 2), "heroes"),
                ("Witness", (25, 2) if visibility == "hidden_birth" else (7, 2), "enemy")):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction=faction,
                action_economy=ActionEconomyConfig(spell_slots={6: 2, 3: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="wisdom")))
            setup_standard_actions(actor)
            if name == "Caster":
                register_spell(actor, spell, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
            actors.append(actor)
        caster, witness = actors
        encounter.initiative_order = [actor.uuid for actor in actors]
        with fixed_dice_faces(15, 1):
            encounter.start_encounter()
        encounter.start_turn()
        system = bind_summoning(game, encounter)
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Before summoning", start_cursor=0, end_cursor=cursor,
            observer_uuid=caster.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        form = "dretch" if family == "fiend" else "wolf"
        row = next(row for row in get_available_actions(caster, legal_only=True).all_actions
                   if row.template_name.endswith("__summon_" + form))
        choice = next(choice for choice in row.valid_targets if choice.position == (4, 2))
        event = execute_available_action(caster, row, choice)
        assert event is not None and not event.canceled
        member = next(iter(system.memberships.values()))
        identity = member.entity.uuid
        origin = member.existence.origin
        member.entity.uses_death_saves = death_saves
        if prone_before_departure:
            member.entity.add_condition(Prone(source_entity_uuid=witness.uuid))
        if visibility == "hidden_departure":
            Entity.update_entity_position(witness, (25, 2))
        if ending == "control_loss":
            if visibility == "reacquire":
                Entity.update_entity_position(witness, (25, 2))
            assert caster.remove_condition("Concentrating")
            assert member.entity.faction != caster.faction
            if visibility != "visible":
                Entity.update_entity_position(witness, (7, 2))
        elif ending == "defeat":
            member.entity.receive_damage(member.entity.get_hp(), DamageType.FORCE, witness.uuid)
            assert identity not in game.entities
        elif ending == "instant_death":
            member.entity.receive_instant_death(witness.uuid)
            assert identity not in game.entities
        else:
            caster.action_economy.reset_all_costs()
            row = next(row for row in get_available_actions(caster, legal_only=True).all_actions
                       if row.behavior_id == "action.summon.dismiss")
            choice = next(choice for choice in row.valid_targets if choice.target_uuid == identity)
            event = execute_available_action(caster, row, choice)
            assert event is not None and not event.canceled
            assert identity not in game.entities
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, cursor) for role, actor in zip(("caster", "witness"), actors)))
        return history, identity, origin
    finally:
        game.close()
        reset_engine_runtime()


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(DATA_ROOT.parent / "rigs" / name
        for name in ("demonbeast01.json", "greywolf.json")))


@pytest.fixture(scope="module", params=("dismiss", "defeat", "control_loss"))
def history_case(request):
    return request.param, summon_history(request.param)


@pytest.mark.parametrize("view", ("caster", "witness"))
def test_recorded_lifetime_faction_and_manifestation_without_native_registry(history_case, data, view):
    ending, (history, identity, _) = history_case
    rolls = dict(DiceRoll._registry)
    native = RecordedSequence.model_validate_json(history.views[view].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(native))
    assert b'summon_origin' not in payload and b'summoner_uuid' not in payload
    assert b'"existence_condition_uuid"' not in payload and b'"control_condition_uuid"' not in payload
    state, roots = decode_player_sequence(payload)
    observed = []
    departures = []
    factions = []
    for root in roots:
        bound = bind_choreography(state, root, data)
        state = reduce_lineage(state, root)
        if identity in state.actors:
            actor = state.actors[identity]
            assert actor.manifestation is (SummonManifestation.FEY_SPIRIT if ending == "control_loss" else SummonManifestation.NATURAL)
            observed.append(actor)
        departures.extend(node.fact for node in root.events
            if isinstance(node.fact, SpatialFact) and node.fact.terminal_departure)
        factions.extend(node.fact for node in root.events if isinstance(node.fact, FactionFact))
        sample = sample_choreography(bound, bound.complete_ms)
        if departures:
            assert all(actor.contact.actor_uuid != str(identity) for actor in scene_actors(sample.displayed, data, {}))
            assert not any(body.actor_uuid == str(identity) for clip in sample.clips for body in clip.sample.bodies)
            for elapsed in (bound.complete_ms, *(at for at, displayed in bound.states
                    if identity in displayed.actors and not displayed.actors[identity].present)):
                frame = sample_body_presentation(bound.before, state, data, elapsed, elapsed, {}, choreography=bound)
                retiring = [cue for cue in bound.entity_lifecycle
                    if cue.phase == "departure" and cue.actor.contact.actor_uuid == str(identity)
                    and cue.start_ms <= elapsed < cue.body_end_ms]
                poses = [pose for pose in frame.poses if pose.actor.contact.actor_uuid == str(identity)]
                # Native presence is gone; only the finite, witnessed dissolve remains.
                assert bool(poses) == bool(retiring)
    assert observed and observed[0].present and observed[0].faction == "heroes"
    if ending == "control_loss":
        assert not departures and factions
        assert state.actors[identity].present and state.actors[identity].faction != "heroes"
        assert state.actors[identity].manifestation is SummonManifestation.FEY_SPIRIT
    else:
        assert len(departures) == 1
        assert not state.actors[identity].present and state.actors[identity].last_visual_position is None
        assert state.senses is not None and identity not in state.senses.entities
        earlier = tuple(row for root in roots for row in root.observations if row.actor.uuid == identity)
        assert earlier
        assert not observe_actors(state, earlier).actors[identity].present
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {} and DiceRoll._registry == rolls


def test_ordinary_native_sight_loss_does_not_retire_a_lifetime():
    history = visibility_history()
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["observer"])))
    subject = history.views["subject"].initialization.observer_uuid
    for root in roots:
        assert not any(isinstance(node.fact, SpatialFact) and node.fact.terminal_departure for node in root.events)
        state = reduce_lineage(state, root)
    assert subject in state.actors and state.actors[subject].present
    assert state.senses is not None and subject not in state.senses.entities


@pytest.mark.parametrize("death_saves", (False, True))
def test_lethal_summon_hit_keeps_witnessed_blood_before_terminal_departure(death_saves):
    history, identity, _ = summon_history("defeat", death_saves=death_saves)
    for view in ("caster", "witness"):
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[view])))
        injuries = [node for root in roots for node in root.events
            if isinstance(node.fact, DamageResultFact) and node.fact.target_entity_uuid == identity]
        injury_node, = injuries
        injury = injury_node.fact
        assert isinstance(injury, DamageResultFact)
        assert injury.body_release is not None
        assert injury.body_release.release_id == "body.blood"
        assert injury.body_release.position == (4, 2)
        departures = [node for root in roots for node in root.events
            if isinstance(node.fact, SpatialFact) and node.fact.terminal_departure]
        departure, = departures
        order = {row.event_uuid: row.source_index for root in roots for row in root.version_rows}
        assert order[injury_node.uuid] < order[departure.uuid]
        for root in roots:
            state = reduce_lineage(state, root)
        assert not state.actors[identity].present


@pytest.mark.parametrize("ending", ("dismiss", "defeat", "instant_death"))
def test_unseen_terminal_departure_does_not_reveal_retirement(ending):
    history, identity, _ = summon_history(ending, visibility="hidden_departure")
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["witness"])))
    assert not any(isinstance(node.fact, SpatialFact) and node.fact.terminal_departure
                   for root in roots for node in root.events)
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.actors[identity].present
    assert state.senses is not None and identity not in state.senses.entities


@pytest.mark.parametrize("visibility", ("hidden_birth", "reacquire"))
def test_native_acquisition_receives_current_material_and_faction_without_unseen_history(visibility, data):
    history, identity, _ = summon_history("control_loss", visibility=visibility)
    payload = encode_player_sequence(project_sequence(history.views["witness"]))
    state, roots = decode_player_sequence(payload)
    received = [row.actor for root in roots for row in root.observations if row.actor.uuid == identity]
    assert received
    if visibility == "hidden_birth":
        assert identity not in state.actors
        assert all(actor.faction != "heroes" for actor in received)
    else:
        assert received[0].faction == "heroes"
    assert received[-1].faction != "heroes"
    assert all(actor.manifestation is SummonManifestation.FEY_SPIRIT for actor in received)
    assert not any(isinstance(node.fact, FactionFact) for root in roots for node in root.events)
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.actors[identity].present
    actor = next(actor for actor in scene_actors(state, data, {}) if actor.contact.actor_uuid == str(identity))
    assert actor.contact.manifestation is SummonManifestation.FEY_SPIRIT
    assert b'summon_origin' not in payload and b'summoner_uuid' not in payload


@pytest.mark.parametrize("quadrant", range(4))
def test_fey_palette_replaces_real_body_rgb_and_preserves_separate_shadow(data, quadrant):
    pygame.init()
    pygame.display.set_mode((1, 1))
    rig = data.rigs["smallscale.demonbeast01"]
    contact = ActorContact("summon", (0, 0), "S", data.rig.TILE_W / TILE_WIDTH, rig_id="smallscale.demonbeast01")
    layers = tuple(RigLayer(slot, categories[0], alpha=.5 if slot == "shadow" else 1.)
                   for slot, categories in rig.slot_categories.items() if slot in ("body", "shadow"))
    rows = load_actor_media(data, ((contact, layers, ("Idle",)),), all_facings=True)
    originals = {key: pygame.image.tobytes(image, "RGBA") for key, image in rows.items()}
    camera = Camera(zoom=1, quadrant=quadrant)
    body = BodySample("summon", "Idle", 0, "S")
    ordinary = {row.role: row.surface for row in actor_draw_commands(data, body, contact, layers, rows, camera)}
    fey = {row.role: row.surface for row in actor_draw_commands(data, body,
        replace(contact, manifestation=SummonManifestation.FEY_SPIRIT), layers, rows, camera)}
    assert ordinary["actor"].get_alpha() == 255 and fey["actor"].get_alpha() == round(255 * .7)
    assert pygame.image.tobytes(ordinary["actor_shadow"], "RGBA") == pygame.image.tobytes(fey["actor_shadow"], "RGBA")
    assert ordinary["actor_shadow"].get_alpha() == fey["actor_shadow"].get_alpha()
    palette = {((color >> 16) & 255, (color >> 8) & 255, color & 255)
               for color in data.body_materials[SummonManifestation.FEY_SPIRIT].palette.colors}
    colors = {tuple(fey["actor"].get_at((x, y)))[:3]
        for x in range(fey["actor"].get_width()) for y in range(fey["actor"].get_height())
        if fey["actor"].get_at((x, y)).a > 0}
    assert colors and colors <= palette
    assert pygame.image.tobytes(ordinary["actor"], "RGBA") != pygame.image.tobytes(fey["actor"], "RGBA")
    assert all(pygame.image.tobytes(image, "RGBA") == originals[key] for key, image in rows.items())


@pytest.mark.parametrize("family", ("animals", "fey", "fiend"))
def test_native_summon_and_dismiss_share_existing_gesture_release(family, data):
    history, identity, _ = summon_history("dismiss", family=family)
    for view in ("caster", "witness"):
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[view])))
        checked = []
        for root in roots:
            fact = root.root.fact
            if not isinstance(fact, (SpellFact, ActionFact)) or fact.behavior_id not in (
                    "spell.conjure_" + family, "action.summon.dismiss"):
                before = reduce_lineage(before, root)
                continue
            group = bind_choreography(before, root, data)
            if isinstance(fact, SpellFact) and group.nodes:
                timeline = group.nodes[0].bound.timeline
                assert timeline.release_ms is not None
                effect_ms = group.nodes[0].start_ms + timeline.release_ms
                caster_id = str(fact.source_entity_uuid)
            else:
                gesture, = group.body_actions
                assert gesture.clip == "Special1" and gesture.enabled
                effect_ms = gesture.effect_ms
                caster_id = gesture.contact.actor_uuid
                assert not gesture.gaps
            assert effect_ms == pytest.approx(8 * 1000 / 12)
            pending = sample_body_presentation(before, group.after, data, effect_ms - 1,
                effect_ms - 1, {}, choreography=group)
            released = sample_body_presentation(before, group.after, data, effect_ms,
                effect_ms, {}, choreography=group)
            caster_pose, = (pose for pose in pending.poses
                           if pose.actor.contact.actor_uuid == caster_id)
            assert caster_pose.body.clip == "Special1" and caster_pose.body.frame == 7
            present_before = any(pose.actor.contact.actor_uuid == str(identity) for pose in pending.poses)
            present_after = any(pose.actor.contact.actor_uuid == str(identity) for pose in released.poses)
            if isinstance(fact, SpellFact):
                assert not present_before and present_after
            else:
                assert present_before and present_after
                assert not released.displayed.actors[identity].present
                cue, = (row for row in group.entity_lifecycle if row.phase == "departure")
                gone = sample_body_presentation(before, group.after, data, cue.body_end_ms,
                    cue.body_end_ms, {}, choreography=group)
                assert not any(pose.body.actor_uuid == str(identity) for pose in gone.poses)
            assert group.after == reduce_lineage(before, root)
            assert sample_body_presentation(before, group.after, data, effect_ms - 1,
                effect_ms - 1, {}, choreography=group) == pending
            before = group.after
            checked.append(fact.behavior_id)
        assert checked == ["spell.conjure_" + family, "action.summon.dismiss"]
