"""Saved Web membership owns actor wraps; field occupancy never substitutes."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pygame
import pytest

from game.animation import BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.asset_types import AssetSpec
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.condition_animation import resolve_condition_appearance
from game.condition_draw import compose_condition_layers
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer
from game.playback_frame import sample_playback_frame
from game.player_facts import ActionFact, SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.player_helpers import player_history
from tests.game.web_scenarios import web_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    data = load_animation_data()
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                  for style in (data.number_style, data.badge_style))
    yield data, fonts
    pygame.quit()


@pytest.fixture(scope="module", params=("mage", "cannon"))
def captured(request):
    return web_history(delivery=request.param)


@pytest.mark.parametrize("role", ("caster", "target"))
def test_saved_web_wrap_contact_save_escape_cleanup_and_seek(rendering, captured, role):
    data, fonts = rendering
    before, roots = player_history(captured, role=role)
    wrapped_seen = escaped_seen = False
    rows = {}
    for root in roots:
        after = reduce_lineage(before, root)
        group = bind_choreography(before, root, data)
        media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})),
                                 data, body_rows=rows)
        group_media = load_choreography_media(group, body_rows=rows)
        target = next(actor for actor in after.actors.values() if actor.name == "Target")
        second = next(actor for actor in after.actors.values() if actor.name == "Second")
        target_appearance = resolve_condition_appearance(target.conditions, data.condition_recipes, data.condition_media)
        second_appearance = resolve_condition_appearance(second.conditions, data.condition_recipes, data.condition_media)
        assert not second_appearance.layers, "Passing the save while inside the same field must not wrap the body"
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.web":
            wrapped_seen = True
            assert len(target_appearance.layers) == 2 and not target_appearance.unsupported
            contact = next(row.start_ms for row in group.conditions
                if row.target_uuid == target.uuid and row.after_appearance.layers and not row.before_appearance.layers)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((9, 5))

                def sample(time):
                    return sample_playback_frame(before, after, data, time, 4000, camera, {}, media, *fonts,
                        choreography=group, choreography_media=group_media)

                def body(frame):
                    return next(row for row in frame.commands
                        if row.evidence[0] == str(target.uuid) and row.evidence[6] == "actor")

                early, current = sample(contact - .001), sample(contact)
                early_target = next(actor for actor in early.actors if actor.contact.actor_uuid == str(target.uuid))
                current_target = next(actor for actor in current.actors if actor.contact.actor_uuid == str(target.uuid))
                assert not early_target.condition.layers and len(current_target.condition.layers) == 2
                assert pygame.image.tobytes(body(current).surface, "RGBA") != pygame.image.tobytes(body(early).surface, "RGBA")
                assert pygame.image.tobytes(body(sample(contact - .001)).surface, "RGBA") == pygame.image.tobytes(body(early).surface, "RGBA")
        if isinstance(root.root.fact, ActionFact) and root.root.fact.name == "Escape Web":
            escaped_seen = True
            assert not target_appearance.layers
            assert after.senses is not None and after.senses.spatial_effects, "The field survives escape"
        before = after
    assert wrapped_seen and escaped_seen
    assert all(not resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media).layers
               for actor in before.actors.values())


def test_back_body_front_registration_and_alpha_follow_real_body_contact(rendering, captured):
    data, _ = rendering
    state, roots = player_history(captured, role="caster")
    for root in roots:
        state = reduce_lineage(state, root)
        if isinstance(root.root.fact, SpellFact):
            break
    actor = next(actor for actor in scene_actors(state, data, {}) if actor.condition.layers)
    rows = {}
    media = load_scene_media((actor,), data, body_rows=rows)
    load_actor_media(data, ((actor.contact, actor.layers, (data.movement_context.walkClip, "Attack1")),),
                     body_rows=rows, all_facings=True)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(actor.contact.grid)
        for clip in ("Idle", data.movement_context.walkClip, "Attack1"):
            contact = replace(actor.contact, grid=(9.25, 5.75), elevation_steps=2,
                              body_lift_px=13, visual_scale=.75, visual_scale_x=.8)
            body = BodySample(contact.actor_uuid, clip, 0, "NE")
            plain = actor_draw_commands(data, body, contact, actor.layers, media, camera)
            wrapped = actor_draw_commands(data, body, contact, actor.layers, media, camera,
                condition=replace(actor.condition, alpha=.5))
            shadow = next(row for row in plain if row.evidence[6] == "actor_shadow")
            wrapped_shadow = next(row for row in wrapped if row.evidence[6] == "actor_shadow")
            assert shadow.destination == wrapped_shadow.destination
            assert pygame.image.tobytes(shadow.surface, "RGBA") == pygame.image.tobytes(wrapped_shadow.surface, "RGBA")
            image = next(row for row in wrapped if row.evidence[6] == "actor").surface
            assert image.get_alpha() == 128, "Shared actor opacity applies once after back/body/front composition"


def test_composition_preserves_offcenter_body_pixels_and_layer_order(rendering):
    data, _ = rendering
    recipe = data.condition_recipes["condition.spell.web.restrained"]
    # Use tiny uniquely colored sources at measured, unequal pivots. This tests
    # composition and registration rather than comparing the compositor to itself.
    behind, front = recipe.persistent.layers
    back_spec = AssetSpec("back", Path("unused"), (7, 3), (5, 2), 1)
    front_spec = AssetSpec("front", Path("unused"), (2, 2), (1, 1), 1)
    layers = (ResolvedConditionLayer(behind, ConditionLayerMedia("Web", "static", {"E": back_spec})),
              ResolvedConditionLayer(front, ConditionLayerMedia("Web", "static", {"E": front_spec})))
    body = pygame.Surface((4, 4), pygame.SRCALPHA); body.fill("red")
    back = pygame.Surface((7, 3), pygame.SRCALPHA); back.fill("green")
    front_image = pygame.Surface((2, 2), pygame.SRCALPHA); front_image.fill("blue")
    rows = {("condition", behind.assetId, "E", 0): back, ("condition", front.assetId, "E", 0): front_image}
    image, point = compose_condition_layers(body, (8, 6), (10, 10), "E", 1, 1, layers, rows)
    assert point == (5, 6)
    assert image.get_at((1, 2))[:3] == (0, 255, 0)  # back extends to the left
    assert image.get_at((3, 2))[:3] == (255, 0, 0)  # body keeps its old position
    assert image.get_at((4, 3))[:3] == (0, 0, 255)  # front covers body at overlap


def test_source_membership_deduplicates_wraps_and_other_restraints_do_not_select_them(rendering, captured):
    data, _ = rendering
    state, roots = player_history(captured, role="caster")
    for root in roots:
        state = reduce_lineage(state, root)
        if isinstance(root.root.fact, SpellFact):
            break
    target = next(actor for actor in state.actors.values() if actor.name == "Target")
    web = next(member for member in target.conditions if member.behavior_id == "condition.spell.web.restrained")
    generic = next(member for member in target.conditions if member.behavior_id == "condition.restrained")
    second_source = replace(web, condition_uuid=uuid4(), event_uuid=uuid4())

    def appearance(members):
        return resolve_condition_appearance(members, data.condition_recipes, data.condition_media)

    assert len(appearance((generic, web, second_source)).layers) == 2
    assert len(appearance((generic, second_source)).layers) == 2
    assert not appearance((generic,)).layers
    assert web.behavior_id is not None
    recipe = data.condition_recipes[web.behavior_id]
    limited = recipe.model_copy(update={"persistent": recipe.persistent.model_copy(update={
        "layers": tuple(layer.model_copy(update={"activeDuring": ("idle",)}) for layer in recipe.persistent.layers)})})
    selective = resolve_condition_appearance((web,), {web.behavior_id: limited}, data.condition_media)
    assert len(selective.layers) == 2 and not selective.unsupported
    assert all(layer.layer.activeDuring == ("idle",) for layer in selective.layers)
