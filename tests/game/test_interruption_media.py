"""Saved Counterspell outcomes preserve incoming art through a finite clear."""

import pygame
import pytest

from game.animation import ProjectileSample
from game.animation_data import load_animation_data
from game.animation_draw import animation_draw_commands
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import choreography_draw_commands, load_choreography_media
from game.combat import BoundCast
from game.interruption_draw import reaction_media_draw_commands
from game.player_facts import SpellFact
from game.presentation_group import presentation_groups, reduce_presentation_group
from game.projection import Camera
from tests.game.interruption_scenarios import interruption_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def animations():
    return load_animation_data()


@pytest.fixture(scope="module")
def graphics():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield
    pygame.quit()


@pytest.fixture(scope="module")
def histories():
    return {
        "flight": interruption_history(blocker="counterspell", spell="fire_bolt"),
        "failed": interruption_history(blocker="counterspell", spell="fireball", blocked=False),
        "direct": interruption_history(blocker="counterspell", spell="sacred_flame"),
    }


@pytest.fixture(scope="module")
def body_history():
    return interruption_history(blocker="counterspell", spell="blur")


def _countered_group(history, role, data):
    state, roots = player_history(history, role=role)
    for presentation in presentation_groups(roots):
        if presentation.reactions:
            group = bind_choreography(state, presentation.primary, data,
                                      reactions=presentation.reactions)
            assert not group.gaps
            assert group.after == reduce_presentation_group(state, presentation)
            assert isinstance(presentation.primary.root.fact, SpellFact)
            return group
        state = reduce_presentation_group(state, presentation)
    raise AssertionError("Saved history has no disclosed Counterspell")


def _pixels(commands):
    return tuple((row.destination, row.blend, row.surface.get_size(),
                  pygame.image.tobytes(row.surface, "RGBA")) for row in commands)


def _visible(commands):
    return any((pygame.surfarray.array3d(row.surface) if row.blend == pygame.BLEND_RGB_ADD
                else pygame.surfarray.array_alpha(row.surface)).any() for row in commands)


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_successful_counter_has_colored_finite_flight_tail_without_contact(
        histories, animations, graphics, role):
    group = _countered_group(histories["flight"], role, animations)
    assert len(group.reaction_media) == 1
    cue = group.reaction_media[0]
    node = next(row for row in group.nodes if row.event_uuid == cue.incoming_event_uuid)
    assert isinstance(node.bound, BoundCast)
    cutoff = node.start_ms + node.bound.timeline.complete_ms
    assert cue.succeeded and cue.start_ms == pytest.approx(cutoff)
    assert cutoff + 50 < cue.complete_ms <= group.complete_ms
    assert cue.timeline is not None and cue.sample is not None
    assert cue.sample.projectiles
    assert all(row.phase == "travel" and row.progress < 1 for row in cue.sample.projectiles)
    assert not cue.sample.delivery_enabled
    assert not group.damage and not group.conditions and not group.residue_reveals
    assert not cue.sample.numbers and not cue.sample.vitals
    tail = sample_choreography(group, cutoff + 50)
    assert (cue, cutoff + 50) in tail.reaction_media
    assert not tail.clips
    media = load_choreography_media(group).casts[cue.incoming_event_uuid]
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus((5, 6))
        original = animation_draw_commands(cue.timeline, cue.sample, media, camera,
                                          include_bodies=False)
        original_pixels = _pixels(original)
        commands = reaction_media_draw_commands(cue, cutoff + 50, media, camera)
        frozen = tuple(row for row in commands
                       if any(isinstance(projectile, ProjectileSample) and projectile.asset_id in row.evidence
                              for projectile in cue.sample.projectiles))
        burst = tuple(row for row in commands if cue.recipe.successByCamera[quadrant] in row.evidence)
        assert _visible(frozen) and _visible(burst)
        assert tuple(row.destination for row in frozen) == tuple(row.destination for row in original)
        for source_frame, cleared_frame in zip(original, frozen, strict=True):
            source_rgb = pygame.surfarray.array3d(source_frame.surface)
            cleared_rgb = pygame.surfarray.array3d(cleared_frame.surface)
            # The shipped mask is binary coverage: remaining pixels retain
            # incoming colors, including premultiplied additive layers.
            assert ((cleared_rgb == source_rgb).all(axis=2) | (cleared_rgb == 0).all(axis=2)).all()
        # Scrubbing the clear must not alter the ordinary source frames.
        reaction_media_draw_commands(cue, cutoff + 400, media, camera)
        again = animation_draw_commands(cue.timeline, cue.sample, media, camera,
                                       include_bodies=False)
        assert _pixels(again) == original_pixels
        assert _pixels(reaction_media_draw_commands(cue, cutoff + 50, media, camera)) == _pixels(commands)
        assert not reaction_media_draw_commands(cue, cue.complete_ms + 1, media, camera)


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_failed_counter_bursts_without_freezing_the_incoming_cast(
        histories, animations, graphics, role):
    group = _countered_group(histories["failed"], role, animations)
    cue, = group.reaction_media
    assert not cue.succeeded
    node = next(row for row in group.nodes if row.event_uuid == cue.incoming_event_uuid)
    assert not node.interrupted
    assert isinstance(node.bound, BoundCast)
    assert any(row.source.damage_applied for row in node.bound.timeline.applications)
    first = sample_choreography(group, cue.start_ms + 25)
    later = sample_choreography(group, cue.start_ms + 75)
    first_cast = next(clip.sample for clip in first.clips if clip.node.event_uuid == node.event_uuid)
    later_cast = next(clip.sample for clip in later.clips if clip.node.event_uuid == node.event_uuid)
    assert first_cast.projectiles and later_cast.projectiles
    assert any(new.progress > old.progress for old, new in zip(first_cast.projectiles, later_cast.projectiles))
    media = load_choreography_media(group).casts[cue.incoming_event_uuid]
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus((5, 6))
        commands = reaction_media_draw_commands(cue, cue.start_ms + 50, media, camera)
        assert _visible(commands)
        assert all(cue.recipe.failureByCamera[quadrant] in row.evidence for row in commands)


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_direct_counter_burst_stays_at_the_casting_actor(
        histories, animations, graphics, role):
    group = _countered_group(histories["direct"], role, animations)
    cue, = group.reaction_media
    assert cue.timeline is not None and cue.sample is not None
    assert cue.succeeded and not cue.sample.projectiles
    assert not group.damage and not group.conditions and not group.residue_reveals
    source = cue.timeline.source.caster
    target = cue.timeline.source.applications[0].target
    assert source.grid != target.grid
    media = load_choreography_media(group).casts[cue.incoming_event_uuid]
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus((5, 6))
        commands = reaction_media_draw_commands(cue, cue.start_ms + 50, media, camera)
        assert _visible(commands)
        assert all(cue.recipe.successByCamera[quadrant] in row.evidence for row in commands)
        assert all(row.evidence[1] == source.grid for row in commands)


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_body_only_self_cast_is_countered_without_applying_its_condition(
        body_history, animations, graphics, role):
    group = _countered_group(body_history, role, animations)
    cue, = group.reaction_media
    incoming = next(body for body in group.body_actions if body.recipe_id == "spell.blur")
    assert cue.succeeded and cue.timeline is None and cue.sample is None
    assert cue.source.actor_uuid == incoming.contact.actor_uuid
    assert cue.start_ms == pytest.approx(incoming.effect_ms)
    assert cue.complete_ms > incoming.complete_ms
    assert not group.nodes and not group.conditions and not group.damage
    assert all(condition.behavior_id != "condition.spell.blur"
               for actor in group.after.actors.values() for condition in actor.conditions)
    preparation = sample_choreography(group, cue.start_ms - 50)
    assert any(body.actor_uuid == incoming.contact.actor_uuid and body.clip == incoming.clip
               and body.frame > 0 for body in preparation.bodies)
    tail = sample_choreography(group, cue.start_ms + 50)
    media = load_choreography_media(group)
    assert not media.casts
    font = pygame.font.Font(None, 20)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus((5, 6))
        commands = choreography_draw_commands(group, tail, media, font, font, camera,
                                             include_bodies=False)
        burst = tuple(row for row in commands if cue.recipe.successByCamera[quadrant] in row.evidence)
        assert _visible(burst)
        assert all(row.evidence[1] == incoming.contact.grid for row in burst)
        assert not reaction_media_draw_commands(cue, cue.complete_ms + 1, None, camera)
