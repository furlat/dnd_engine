"""Accepted hand accents use actual native cast release and viewed source poses."""

from dataclasses import replace
from pathlib import Path

import pygame
import pytest

from game.animation import ActorContact, CastInput, compile_cast, sample_cast, view_facing
from game.animation_data import load_animation_data
from game.cast_media import cast_media_draw_commands, cast_media_placement
from game.choreography import bind_choreography
from game.combat import BoundCast, actor_contact
from game.player_facts import SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera, TILE_WIDTH, project_screen
from tests.game.player_helpers import player_history
from tests.game.test_summoning_presentation import summon_history


# First measured visible palm at release frame 8 in the accepted Special1
# hand-sockets.json. These are full 128px cell coordinates, not effect pivots.
RELEASE_PALMS = {
    "E": (79., 57.), "SE": (60., 66.), "S": (55., 66.75), "SW": (47.6, 62.2),
    "W": (50.833333333333336, 64.83333333333333), "NW": (54.8, 66.6),
    "N": (59., 51.), "NE": (82.4, 59.8),
}
PREPARATION_PALMS = {
    "E": (77.5, 52.5), "SE": (59.5, 66.5), "S": (48.8, 66.6), "SW": (44.25, 57.),
    "W": (52., 66.75), "NW": (48.8, 59.), "N": (54.5, 50.5), "NE": (85.4, 60.8),
}


@pytest.fixture(scope="module")
def data():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        yield load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))
        pygame.quit()


def draw_signature(commands):
    return tuple((row.destination, row.blend, row.evidence,
                  pygame.image.tobytes(row.surface, "RGBA")) for row in commands)


@pytest.mark.parametrize("family,material", (("animals", "natural"), ("fey", "fey_spirit"), ("fiend", "fiend")))
def test_native_summon_uses_shared_cast_media_at_original_release_and_seeks(data, family, material):
    history, _, _ = summon_history("dismiss", family=family)
    for view in ("caster", "witness"):
        before, roots = player_history(history, role=view)
        checked = False
        for root in roots:
            fact = root.root.fact
            if not isinstance(fact, SpellFact) or fact.behavior_id != "spell.conjure_" + family:
                before = reduce_lineage(before, root)
                continue
            group = bind_choreography(before, root, data)
            node, = group.nodes
            assert isinstance(node.bound, BoundCast) and not group.gaps
            timeline = node.bound.timeline
            assert timeline.recipe.cast.actionClip == "Special1"
            assert timeline.release_ms == pytest.approx(8 * 1000 / 12)
            assert {track.assetId for track in timeline.recipe.media} == {
                f"summoning.{material}.cast.back", f"summoning.{material}.cast.front"}
            assert all(track.startOffsetMs == -250 and track.durationMs == 750
                       and track.fps == 32 for track in timeline.recipe.media)
            start = timeline.release_ms - 250
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=1).with_focus(timeline.source.caster.grid)
                def draws(at):
                    return cast_media_draw_commands(timeline, sample_cast(timeline, at), camera, None, {})
                assert not draws(start - .01)
                release = draws(timeline.release_ms)
                assert release and {row.evidence[-1] for row in release} == {8}
                assert any(pygame.mask.from_surface(row.surface, threshold=1).count() for row in release)
                assert release[0].key < release[-1].key
                assert not draws(start + 750)
                assert draw_signature(draws(timeline.release_ms)) == draw_signature(release)
            assert group.after == reduce_lineage(before, root)
            checked = True
            before = group.after
        assert checked


def test_world_media_camera_bank_does_not_choose_the_casters_viewed_hand(data):
    for facing in data.rig.FACING_ROW:
        contact = ActorContact("caster", (2, 3), facing, 1.3, elevation_steps=1, visual_scale_x=.8)
        timeline = compile_cast(data, "spell.conjure_animals", CastInput("summon", contact, ()))
        track = timeline.recipe.media[0]
        body, = sample_cast(timeline, timeline.release_ms).bodies
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=1)
            placement = cast_media_placement(timeline, track, contact, camera, body)
            palm = RELEASE_PALMS[view_facing(body.facing, quadrant, data)]
            ground = project_screen(contact.grid, camera, elevation_steps=1)
            body_scale = contact.visual_scale * TILE_WIDTH / data.rig.TILE_W
            assert placement.anchor == pytest.approx((ground[0] + (palm[0] - 64) * body_scale * .8,
                                                      ground[1] + (palm[1] - 87) * body_scale))
            assert placement.scale == pytest.approx(.8), "effect pixels do not inherit creature size"
            preparation, = sample_cast(timeline, 500).bodies
            earlier = cast_media_placement(timeline, track, contact, camera, preparation)
            palm = PREPARATION_PALMS[view_facing(preparation.facing, quadrant, data)]
            assert earlier.anchor == pytest.approx((ground[0] + (palm[0] - 64) * body_scale * .8,
                                                    ground[1] + (palm[1] - 87) * body_scale))
            # A later Idle body cannot index the old Special1 preparation track.
            idle = cast_media_placement(timeline, track, contact, camera, replace(body, clip="Idle", frame=3))
            assert idle.anchor == placement.anchor


@pytest.mark.parametrize("number", (2, 8))
def test_fixed_casters_keep_their_original_preparation_and_measured_cast_origin(data, number):
    # A real native recording supplies all facts; only its rendering rig changes.
    history, _, _ = summon_history("dismiss", family="fey")
    before, roots = player_history(history, role="caster")
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == "spell.conjure_fey":
            actor = before.actors[fact.source_entity_uuid]
            contact = replace(actor_contact(before, actor, data), rig_id=f"smallscale.goblin{number:02d}")
            group = bind_choreography(before, root, data, contacts={contact.actor_uuid: contact})
            assert not group.gaps and not group.nodes
            gesture, = group.body_actions
            assert gesture.clip == "Attack2" and gesture.effect_ms == 500
            assert not gesture.cast_layers, "the fixed clip owns its original preparation pixels"
            assert group.after == reduce_lineage(before, root)
            return
        before = reduce_lineage(before, root)
    pytest.fail("native history did not include the summon cast")
