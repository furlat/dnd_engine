"""Real portal gallery inputs retain independent endpoint grants after reset."""

from uuid import UUID
from math import ceil

import pygame
import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.animation_data import load_animation_data
from game.choreography import BoundChoreography, bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media, load_motion_media
from game.animation_draw import LoadedBodyRows
from game.assets import prop_animation_frame
from game.motion import bind_motion, sample_motion
from game.playback_frame import sample_playback_frame
from game.portal_draw import portal_draw_commands
from game.player_facts import ActionFact, DamageFact, MovementFact, PortalTransferFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage, stage_lineage
from game.replay import RecordedSequence
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.world_animation import sample_world_transitions
from tests.game.portal_scenarios import portal_history


def check_portal_cues(group: BoundChoreography, program: str, role: str) -> int:
    """Check observable crossing phases in the real lineage's local clock."""
    assert not group.gaps, (program, role, group.gaps)
    for cue in group.portals:
        assert program != "blocked-exit", "Canceled transfer must have no finite portal crossing."
        assert (cue.art.hatch is not None) is (program != "bare-walk")
        assert (cue.departure is not None) is (role != "arrival")
        assert (cue.arrival is not None) is (role != "departure")
        if role == "arrival":
            assert cue.portal_uuid is None
        else:
            assert cue.portal_uuid is not None
        if cue.art.hatch is not None and cue.departure is not None:
            openings = [change for change in group.world_transitions
                        if change.identity == cue.portal_uuid and change.field == "trap_state"
                        and change.current == "activated"]
            if program in ("hatch-open", "hatch-open-jump"):
                assert not openings, "An already open hatch does not reopen."
                assert cue.fall_start_ms == cue.start_ms
            else:
                opening, = openings
                assert opening.start_ms == pytest.approx(cue.start_ms)
                assert cue.fall_start_ms - opening.start_ms == pytest.approx(50)
        if cue.departure is not None:
            assert cue.departure.grid == (3, 2)
            falling = sample_choreography(group, (cue.fall_start_ms + cue.disappear_ms) / 2)
            contact = next(contact for contact in falling.contacts if contact.actor_uuid == cue.actor_uuid)
            assert contact.grid == (3, 2) and contact.body_lift_px < 0
            early = sample_choreography(group, cue.fall_start_ms + (cue.disappear_ms - cue.fall_start_ms) / 4)
            early_contact = next(contact for contact in early.contacts if contact.actor_uuid == cue.actor_uuid)
            assert contact.body_lift_px == pytest.approx(early_contact.body_lift_px * 4), "The fall accelerates."
            assert cue.actor_uuid not in falling.hidden_actors
            assert (cue.actor_uuid in sample_choreography(group, cue.disappear_ms).hidden_actors) is (
                cue.arrival is None or cue.arrival_ms > cue.disappear_ms)
        if cue.arrival is not None:
            assert cue.arrival.grid == (17, 2)
            assert cue.arrival_ms - cue.exit_open_ms >= cue.art.exit.opening_frames * 1000 / cue.art.exit.fps
            assert cue.complete_ms > cue.exit_close_ms > cue.settled_ms > cue.arrival_ms
            prior = sample_choreography(group, cue.arrival_ms - .001)
            arrived = sample_choreography(group, cue.arrival_ms)
            assert (cue.actor_uuid in prior.hidden_actors) is (
                cue.departure is None or cue.arrival_ms > cue.disappear_ms)
            assert cue.actor_uuid not in arrived.hidden_actors
            arrival_contact = next(contact for contact in arrived.contacts if contact.actor_uuid == cue.actor_uuid)
            assert arrival_contact.grid == (17, 2) and arrival_contact.body_lift_px < 0
            emerged = sample_choreography(group, cue.settled_ms)
            assert next(contact for contact in emerged.contacts if contact.actor_uuid == cue.actor_uuid).body_lift_px == 0
            tail = sample_choreography(group, (cue.arrival_ms + cue.exit_close_ms) / 2)
            assert next(contact for contact in tail.contacts if contact.actor_uuid == cue.actor_uuid).grid == (17, 2)
            assert prior.displayed.senses is not None and arrived.displayed.senses is not None
            if role == "traveler":
                assert prior.displayed.senses.position != (17, 2)
                assert arrived.displayed.senses.position == (17, 2)
            else:
                identity = UUID(cue.actor_uuid)
                assert identity not in prior.displayed.senses.entities
                assert arrived.displayed.senses.entities[identity].position == (17, 2)
            sample_choreography(group, cue.complete_ms)
            assert sample_choreography(group, cue.arrival_ms - .001) == prior
    return len(group.portals)


@pytest.mark.parametrize("program", (
    "hatch-walk", "hatch-jump", "bare-walk", "blocked-exit", "occupied-activation", "hatch-open", "hatch-visible",
    "hatch-open-jump",
))
def test_portal_gallery_uses_native_commands_and_only_disclosed_endpoints(program):
    history = portal_history(program=program)
    assert set(history.views) == {"traveler", "departure", "arrival"}
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    data = load_animation_data()
    for role, saved in history.views.items():
        native = RecordedSequence.model_validate_json(saved.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        payload = encode_player_sequence(project_sequence(native))
        assert b"exit_position" not in payload and b"target_condition_uuid" not in payload
        before, roots = decode_player_sequence(payload)
        facts = [node.fact for root in roots for node in root.events]
        crossings = {node.uuid: node.fact for root in roots for node in root.events
                     if isinstance(node.fact, PortalTransferFact)}
        blocked = program == "blocked-exit"
        if blocked and role != "traveler":
            assert not crossings, "The canceled private transfer produces no witness crossing."
        else:
            crossing, = crossings.values()
            assert crossing.committed is not blocked
            assert crossing.start_position == (None if role == "arrival" else (3, 2))
            assert crossing.end_position == (None if blocked or role == "departure" else (17, 2))
            if role == "arrival":
                assert crossing.portal_uuid is None
        if role == "departure":
            movements = [fact for fact in facts if isinstance(fact, MovementFact)]
            assert all(fact.end_position != (17, 2) for fact in movements)
        if program == "occupied-activation" and role != "arrival":
            assert any(isinstance(fact, ActionFact) and fact.name == "Activate Trap" for fact in facts)
        state = before
        portal_count = 0
        for root in roots:
            motion = bind_motion(state, root, data)
            if motion is not None:
                for reaction in motion.reactions:
                    portal_count += check_portal_cues(reaction.choreography, program, role)
                    if reaction.choreography.portals and motion.legs:
                        assert reaction.start_ms >= motion.legs[-1].end_ms, "Finish incoming motion before falling."
                        if program == "hatch-open-jump":
                            assert len(motion.legs) == 1
                            assert all(reaction.start_ms + cue.fall_start_ms == motion.legs[-1].end_ms
                                       for cue in reaction.choreography.portals), "No landing pause before the open hatch fall."
                    if role == "traveler":
                        for cue in reaction.choreography.portals:
                            for local in (cue.arrival_ms, cue.settled_ms):
                                arrived_motion = sample_motion(motion, data, reaction.start_ms + local)
                                assert arrived_motion.contact is not None
                                assert arrived_motion.contact.grid == (17, 2)
                                assert (arrived_motion.contact.body_lift_px < 0) is (local < cue.settled_ms)
                halfway = motion.complete_ms / 2
                paused = sample_motion(motion, data, halfway)
                assert sample_motion(motion, data, halfway) == paused
                sample_motion(motion, data, motion.complete_ms)
                state = reduce_lineage(state, root)
                assert sample_motion(motion, data, halfway) == paused
                continue
            group = bind_choreography(state, root, data)
            portal_count += check_portal_cues(group, program, role)
            halfway = group.complete_ms / 2
            paused = sample_choreography(group, halfway)
            assert sample_choreography(group, halfway) == paused
            sample_choreography(group, group.complete_ms)
            state = reduce_lineage(state, root)
            assert sample_choreography(group, halfway) == paused
        assert portal_count == (0 if blocked else 1), (program, role)
        assert state.senses is not None
        traveler = next((actor for actor in state.actors.values() if actor.name == "Traveler"), None)
        if role == "traveler":
            assert state.senses.position == ((3, 2) if blocked else (17, 2))
        elif role == "arrival" and not blocked:
            assert traveler is not None
            assert state.senses.entities[traveler.uuid].position == (17, 2)
        elif role == "departure" and not blocked:
            assert traveler is not None and traveler.uuid not in state.senses.entities
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_remote_exit_opening_draws_only_where_current_subjective_sight_allows_it():
    history = portal_history(program="hatch-visible")
    data = load_animation_data()
    pygame.init()
    pygame.display.set_mode((320, 240))
    try:
        for role in ("traveler", "arrival"):
            state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
            checked = False
            for root in roots:
                motion = bind_motion(state, root, data)
                groups = ([reaction.choreography for reaction in motion.reactions] if motion is not None
                          else [bind_choreography(state, root, data)])
                for group in groups:
                    for cue in group.portals:
                        assert cue.arrival is not None
                        before_arrival = (cue.exit_open_ms + cue.arrival_ms) / 2
                        opening = sample_choreography(group, before_arrival)
                        arrived = sample_choreography(group, cue.arrival_ms)
                        assert opening.displayed.senses is not None
                        assert ((17, 2) in opening.displayed.senses.visible) is (role == "arrival")
                        for quadrant in range(4):
                            camera = Camera(quadrant=quadrant)
                            commands = portal_draw_commands(opening.displayed, data, before_arrival,
                                camera, (), opening.portals)
                            assert any(command[4][6] == "portal_exit" for command in commands) is (role == "arrival")
                            commands = portal_draw_commands(arrived.displayed, data, cue.arrival_ms,
                                camera, (), arrived.portals)
                            assert any(command[4][6] == "portal_exit" for command in commands)
                            ended = sample_choreography(group, cue.complete_ms)
                            commands = portal_draw_commands(ended.displayed, data, cue.complete_ms,
                                camera, (), ended.portals)
                            assert not any(command[4][6] == "portal_exit" for command in commands)
                        checked = True
                state = reduce_lineage(state, root)
            assert checked, role
            assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    finally:
        pygame.quit()


def test_real_exit_hazard_plays_at_ground_settle_while_arrival_is_already_visible():
    history = portal_history(arrival_spikes=True)
    data = load_animation_data()
    for role in ("traveler", "arrival"):
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
        checked = False
        for root in roots:
            motion = bind_motion(state, root, data)
            groups = ([reaction.choreography for reaction in motion.reactions] if motion is not None
                      else [bind_choreography(state, root, data)])
            for group in groups:
                for cue in group.portals:
                    assert cue.arrival is not None and not group.gaps
                    arriving = sample_choreography(group, cue.arrival_ms)
                    prior = sample_choreography(group, cue.arrival_ms - .001)
                    airborne = sample_choreography(group, cue.settled_ms - .001)
                    settled = sample_choreography(group, cue.settled_ms)
                    identity = UUID(cue.actor_uuid)
                    assert cue.actor_uuid not in arriving.hidden_actors
                    assert next(contact for contact in arriving.contacts
                                if contact.actor_uuid == cue.actor_uuid).body_lift_px < 0
                    assert next(contact for contact in settled.contacts
                                if contact.actor_uuid == cue.actor_uuid).grid == (17, 2)
                    if role == "traveler":
                        assert arriving.displayed.actors[identity].normal_hp == 20
                        assert airborne.displayed.actors[identity].normal_hp == 20
                        assert settled.displayed.actors[identity].normal_hp == 19
                        damage, = group.damage
                        assert damage.timing.start_ms == cue.settled_ms
                        assert damage.contact.grid == (17, 2), "Arrival damage belongs at the exit, not the old walk contact."
                        assert arriving.displayed.senses is not None
                        spike_uuid, spike = next((identity, effect)
                            for identity, effect in arriving.displayed.senses.spatial_effects.items()
                            if effect.content_ref.content_id == "spatial_effect.environment.spike_trap")
                        art = data.world_animations[spike.content_ref.content_id]
                        for time, expected in ((cue.arrival_ms, "spikes.e.0"), (cue.settled_ms, "spikes.e.0"),
                                               (cue.settled_ms+250, "spikes.e.6")):
                            transition = next((sample for sample in sample_world_transitions(group.world_transitions, time)
                                               if sample.transition.identity == spike_uuid), None)
                            assert spike.trap_state is not None
                            resource, _ = prop_animation_frame(art, "e", spike.trap_state.value, transition)
                            assert resource == expected, "A late snapshot must not make spikes rise, rewind, then rise again."
                    else:
                        # This observer first receives the already injured
                        # creature; no unobserved earlier HP/hit is invented.
                        assert arriving.displayed.actors[identity].normal_hp == 19
                        assert identity not in prior.displayed.actors
                        assert cue.actor_uuid in prior.hidden_actors
                        assert not any(isinstance(node.fact, DamageFact) for node in root.events)
                        assert not group.damage
                    assert sample_choreography(group, cue.arrival_ms) == arriving
                    checked = True
            state = reduce_lineage(state, root)
        assert checked, role


def test_exit_hazard_saved_replay_keeps_contacts_and_world_support_coherent_in_every_frame(monkeypatch):
    """Exercise the frame compositor which failed although cue sampling passed."""
    history = portal_history(arrival_spikes=True)
    data = load_animation_data()
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((640, 480))
    font = pygame.font.Font(None, 24)
    try:
        for role, saved in history.views.items():
            before, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
            for root in roots:
                after = reduce_lineage(before, root)
                motion = bind_motion(before, root, data)
                group = None if motion is not None else bind_choreography(before, root, data)
                groups = ([reaction.choreography for reaction in motion.reactions] if motion is not None
                          else [group] if group is not None else [])
                cue = next((cue for group in groups for cue in group.portals), None)
                if cue is None:
                    before = after
                    continue
                offset = next((reaction.start_ms for reaction in motion.reactions
                               if cue in reaction.choreography.portals), 0) if motion is not None else 0
                rows: LoadedBodyRows = {}
                bodies = load_scene_media(scene_actors(stage_lineage(before, root), data, {}), data, body_rows=rows)
                reactions = load_motion_media(motion, data, body_rows=rows) if motion is not None else None
                media = load_choreography_media(group, body_rows=rows) if group is not None else None
                duration = motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0
                times = sorted({min(index*1000/24, duration) for index in range(ceil(duration*24/1000)+1)}
                               | {offset+cue.arrival_ms-.001, offset+cue.arrival_ms, offset+cue.settled_ms})
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((17, 2))
                    for elapsed in times:
                        frame = sample_playback_frame(before, after, data, elapsed, elapsed, camera, {}, bodies,
                            font, font, choreography=group, choreography_media=media, motion=motion,
                            reaction_media=reactions)
                        if role == "traveler" and elapsed == offset+cue.arrival_ms-.001:
                            assert frame.displayed.senses is not None
                            assert (17, 2) not in frame.displayed.senses.visible
                        if role == "traveler" and elapsed == offset+cue.arrival_ms:
                            assert frame.displayed.senses is not None
                            assert frame.displayed.senses.position == (17, 2)
                            assert (17, 2) in frame.displayed.senses.visible
                            assert (17, 2) in frame.displayed.tiles
                            assert frame.displayed.actors[UUID(cue.actor_uuid)].normal_hp == 20
                        if role == "traveler" and elapsed == offset+cue.settled_ms:
                            assert frame.displayed.actors[UUID(cue.actor_uuid)].normal_hp == 19
                            actor = next(actor for actor in frame.actors if actor.contact.actor_uuid == cue.actor_uuid)
                            assert actor.contact.grid == (17, 2) and actor.contact.body_lift_px == 0
                    assert frame.complete and frame.displayed == after
                before = after
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    finally:
        pygame.quit()
