"""Real terrain contact consequences survive saved, observer-specific replay."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest

from dnd.actions import Move, Jump
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, SpatialChangeType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from dnd.spells.conjuration import Grease
from dnd.spells.transmutation import SpikeGrowth
from dnd.types.world import OccupancyLayer
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.motion_media import bind_motion_media, choreography_motion_media, motion_media_draw_commands
from game.player_facts import DamageFact, SavingThrowFact, SpatialFact
from game.player_reduction import decode_player_sequence, reduce_lineage
from game.projection import Camera
from game.spatial_contact_media import bind_spatial_contacts
from tests.game.test_spell14_native_facts import actors, saved_views


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data()
    pygame.quit()


def terrain_walk(spell, *, die=20, known=True, jump_end=None):
    caster, walker = actors()
    if known:
        for actor in (caster, walker):
            actor.skill_set.get_skill("perception").skill_bonus.self_static.add_value_modifier(
                NumericalModifier.create(name="Observed terrain", value=50, source_entity_uuid=actor.uuid))
    start = EventQueue.event_cursor()
    center = (5, 4) if spell is Grease else (7, 4)
    event = spell(source_entity_uuid=caster.uuid, end_position=center, template=False).apply()
    assert event is not None and not event.canceled
    zone, = get_map().get_spatial_conditions()
    with fixed_dice_faces(*((die,) if spell is Grease else (2, 2, 2, 2))):
        move = (Jump(source_entity_uuid=walker.uuid, end_position=jump_end, template=False).apply()
                if jump_end is not None else Move(source_entity_uuid=walker.uuid, end_position=(5, 4),
                    path=[(3, 4), (4, 4), (5, 4)], prefer_safe=False, template=False).apply())
    assert move is not None and not move.canceled, move.status_message if move else None
    views = saved_views((caster, walker), start)
    return caster.uuid, walker.uuid, zone, views


@pytest.mark.parametrize("die,succeeds", ((20, True), (1, False)))
def test_grease_entries_splash_with_either_save_outcome_without_pausing_walk(rendering, die, succeeds):
    _, _, zone, views = terrain_walk(Grease, die=die)
    for payload in views.values():
        before, heads = decode_player_sequence(payload)
        before = reduce_lineage(before, heads[0])
        motion = bind_motion(before, heads[1], rendering)
        assert motion is not None
        saves = [node.fact for node in heads[1].events if isinstance(node.fact, SavingThrowFact)]
        assert saves and saves[0].succeeded is succeeds
        entries = [node for node in heads[1].events if isinstance(node.fact, SpatialFact)
                   and node.fact.change_type is SpatialChangeType.ENTITY_ENTERED
                   and node.fact.occupancy_layer is OccupancyLayer.GROUND
                   and node.fact.position in zone.affected_positions]
        cues = bind_motion_media(motion, rendering, 0.)
        contacts = [cue for cue in cues if cue.media.track.id == "grease.contact"]
        assert len(contacts) == len(entries) > 0
        assert {cue.media.event_uuid for cue in contacts} == {node.uuid for node in entries}
        binding = rendering.spatial_media[zone.content_ref.content_id]
        quiet = replace(rendering, spatial_media={**rendering.spatial_media,
            zone.content_ref.content_id: binding.model_copy(update={"contactMedia": {}})})
        without_media = bind_motion(before, heads[1], quiet)
        assert without_media is not None and motion.complete_ms == without_media.complete_ms
        for cue in contacts:
            assert cue.media.end_ms-cue.media.start_ms == pytest.approx(500.)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(cue.media.position)
                drawn = motion_media_draw_commands((cue,), cue.media.start_ms+100., camera)
                assert drawn and all(command.surface.get_bounding_rect().width for command in drawn)
                assert not motion_media_draw_commands((cue,), cue.media.end_ms, camera)
    assert EventQueue.event_cursor() == 0


def test_spike_contact_requires_its_applied_damage_not_other_damage_on_same_ground(rendering):
    caster_id, walker_id, zone, views = terrain_walk(SpikeGrowth)
    for payload in views.values():
        before, heads = decode_player_sequence(payload)
        before = reduce_lineage(before, heads[0])
        motion = bind_motion(before, heads[1], rendering)
        assert motion is not None
        applied = [node for node in heads[1].events if isinstance(node.fact, DamageFact)
                   and node.fact.stage == "applied"]
        assert applied and all(node.fact.effect_id == zone.content_ref.identity_key for node in applied)
        cues = [cue for cue in bind_motion_media(motion, rendering, 0.) if cue.media.track.id == "spike_growth.contact"]
        assert {cue.media.event_uuid for cue in cues} == {node.uuid for node in applied}
        assert len(cues) == len(applied)
        after = reduce_lineage(before, heads[1])
        duplicate_id = uuid4()
        # An additional observed owner cannot duplicate a single applied packet.
        overlap = replace(after, senses=replace(after.senses, spatial_effects={**after.senses.spatial_effects,
            duplicate_id: after.senses.spatial_effects[zone.uuid]}))
        assert len(bind_spatial_contacts(overlap, applied[-1], rendering, 0., {})) == 1
        unrelated = replace(applied[-1], fact=replace(applied[-1].fact, effect_id=None,
            source_entity_uuid=caster_id, target_entity_uuid=walker_id, damage_type=DamageType.PIERCING))
        assert not bind_spatial_contacts(after, unrelated, rendering, 0., {})
        hidden_floor = replace(after, senses=replace(after.senses, visible=set()))
        assert not bind_spatial_contacts(hidden_floor, applied[-1], rendering, 0., {})


def test_hidden_spikes_do_not_reveal_their_identity_through_damage_media(rendering):
    _, walker_id, zone, views = terrain_walk(SpikeGrowth, known=False)
    before, heads = decode_player_sequence(views[walker_id])
    before = reduce_lineage(before, heads[0])
    assert zone.uuid not in before.senses.spatial_effects
    applied = [node.fact for node in heads[1].events if isinstance(node.fact, DamageFact)
               and node.fact.stage == "applied"]
    assert applied and all(fact.effect_id is None for fact in applied)
    motion = bind_motion(before, heads[1], rendering)
    assert motion is not None
    assert not any(cue.media.track.id == "spike_growth.contact" for cue in bind_motion_media(motion, rendering, 0.))


@pytest.mark.parametrize("endpoint,contacts", (((6, 4), 0), ((5, 4), 1)))
def test_grease_jump_splashes_only_on_grounded_landing(rendering, endpoint, contacts):
    _, _, _, views = terrain_walk(Grease, jump_end=endpoint)
    for payload in views.values():
        before, heads = decode_player_sequence(payload)
        before = reduce_lineage(before, heads[0])
        group = bind_choreography(before, heads[1], rendering)
        cues = choreography_motion_media(group, rendering, 0.)
        assert len([cue for cue in cues if cue.media.track.id == "grease.contact"]) == contacts
    assert not Entity.get_all_entities()
