"""Actual Thorns damage drives local source motion without changing native rules."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import actor_contact, actor_is_visible
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.wall_assembly_media import assembly_media_draw_commands
from tests.game.assembly_scenarios import assembly_history


@pytest.fixture(scope='module')
def received():
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = load_animation_data()
    history = assembly_history(program='thorns')
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views['recipient'])))
    retained = {}
    now = 0.
    selected = None
    for root in roots:
        group = bind_choreography(before, root, data)
        assert not group.gaps
        retained = register_spatial_lifetimes(retained, before, data,
            absolute_start_ms=now, lineage=root, choreography=group)
        after = reduce_lineage(before, root)
        for owner, record in retained.items():
            if record.removed_ms is None and any(not row.formation for row in record.damage_contacts):
                contacts = tuple(actor_contact(before, actor, data, 'S')
                    for actor in before.actors.values() if actor_is_visible(before, actor))
                selected = owner, record, contacts
        before = after
        now += group.complete_ms+2500
    assert selected is not None
    yield data, *selected
    pygame.quit()


def pixels(commands, camera):
    image = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    for command in commands:
        image.blit(command.surface, command.destination)
    return pygame.image.tobytes(image, 'RGBA')


@pytest.mark.parametrize('quarter', range(4))
def test_native_local_damage_pull_replays_at_contact_and_stops(received, quarter):
    data, owner, record, contacts = received
    effect = record.effect
    binding = data.spatial_media[effect.content_ref.content_id]
    camera = Camera(quadrant=quarter, zoom=.5).with_focus((8.5, 7))
    visible = {c.actor_uuid for c in contacts}
    hit = next(row for row in record.damage_contacts
        if not row.formation and row.recipient.actor_uuid in visible)
    damage = tuple((row.recipient, row.at_ms) for row in record.damage_contacts)

    def draw(at, events=damage, bodies=contacts):
        return assembly_media_draw_commands(effect, owner, data, binding, at, camera,
            record.applied_ms, None, contacts=bodies, damage_contacts=events)

    contact = draw(hit.at_ms)
    quiet = draw(hit.at_ms, ())
    assert contact and quiet
    assert all(c.volume is not None and c.owner == str(owner) for c in contact)
    assert pixels(contact, camera) != pixels(quiet, camera)
    assert pixels(contact, camera) == pixels(draw(hit.at_ms), camera)
    assert pixels(draw(hit.at_ms+650), camera) == pixels(draw(hit.at_ms+650, ()), camera)
    # A previously received damage location cannot reveal an actor after sight
    # is lost, nor make an empty field repeat that person's pulse.
    assert pixels(draw(hit.at_ms, bodies=()), camera) == pixels(draw(hit.at_ms, (), ()), camera)
    # A body carried above the wall's support is not a ground contact merely
    # because its support cell still lies inside that wall.
    airborne = tuple(replace(c, body_lift_px=256) for c in contacts)
    assert pixels(draw(hit.at_ms, bodies=airborne), camera) == pixels(draw(hit.at_ms, (), ()), camera)
    assert not assembly_media_draw_commands(effect, owner, data, binding, hit.at_ms+1200,
        camera, record.applied_ms, hit.at_ms, contacts=contacts, damage_contacts=damage)
