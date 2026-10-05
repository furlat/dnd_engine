"""Received Slow outcomes own the envelope through movement, looping and clear."""

from dataclasses import replace
from types import MappingProxyType
from uuid import uuid4

import pygame
import pytest

from dnd.core.condition_types import ConditionCategory
from game.actor_facts import ConditionFact
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.combat import BoundCast
from game.condition_animation import ConditionAppearance, resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.playback_frame import sample_playback_frame
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from tests.game.slow_scenarios import slow_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.fixture(scope="module", params=(False, True))
def captured(request):
    return request.param, slow_history(saved=request.param)


@pytest.mark.parametrize("observer", ("caster", "recipient"))
def test_native_save_outcomes_movement_and_clear_survive_paired_playback(data, captured, observer):
    saved, history = captured
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
    initial_hp = {actor.uuid: actor.normal_hp for actor in before.actors.values()}
    native_owners = set()
    drawn = set()
    recipe = data.condition_recipes["condition.spell.slow"]
    plain = replace(data, condition_recipes=MappingProxyType({**data.condition_recipes,
        "condition.spell.slow": recipe.model_copy(update={"persistent":
            recipe.persistent.model_copy(update={"layers": ()})})}))
    font = pygame.font.Font(None, 14)
    for root in roots:
        group = bind_choreography(before, root, data)
        assert not group.gaps
        for clip in group.nodes:
            if isinstance(clip.bound, BoundCast):
                assert clip.bound.timeline.recipe.definitionRef.content_id == "spell.slow"
                assert not clip.bound.timeline.recipe.media
        before = reduce_lineage(before, root)
        native_owners.update(actor.uuid for actor in before.actors.values()
            if any(condition.behavior_id == "condition.spell.slow" for condition in actor.conditions))
        rows = {}
        bodies = load_scene_media(scene_actors(before, data, {}), data, body_rows=rows)
        media = load_choreography_media(group, body_rows=rows)
        # Main playback uses the native post-action state during a readable hold.
        for quadrant in range(4):
            frame = sample_playback_frame(group.before, group.after, data,
                group.complete_ms + 250, group.complete_ms + 250,
                Camera(quadrant=quadrant), {}, bodies, font, font,
                choreography=group, choreography_media=media)
            reference = sample_playback_frame(group.before, group.after, plain,
                group.complete_ms + 250, group.complete_ms + 250,
                Camera(quadrant=quadrant), {}, bodies, font, font,
                choreography=group, choreography_media=media)
            unadorned = {command.owner: command for command in reference.commands if command.role == "actor"}
            for command in frame.commands:
                if command.role != "actor":
                    continue
                original = unadorned[command.owner]
                differs = ((command.destination, command.surface.get_size(),
                    pygame.image.tobytes(command.surface, "RGBA")) !=
                    (original.destination, original.surface.get_size(),
                    pygame.image.tobytes(original.surface, "RGBA")))
                if saved:
                    assert not differs
                if differs:
                    drawn.add(command.owner)
    recipients = {actor.uuid for actor in before.actors.values() if actor.name in ("Recipient", "Second")}
    assert native_owners == (set() if saved else recipients)
    assert drawn == (set() if saved else {str(actor) for actor in recipients})
    assert not any(condition.behavior_id == "condition.spell.slow"
        for actor in before.actors.values() for condition in actor.conditions)
    assert {actor.uuid: actor.normal_hp for actor in before.actors.values()} == initial_hp
    recipient = next(actor for actor in before.actors.values() if actor.name == "Recipient")
    assert recipient.last_visual_position == (5, 8)


def test_reacquired_loop_skips_onset_and_removal_continues_current_phase(data):
    actor, owner = uuid4(), uuid4()
    fact = ConditionFact(event_uuid=uuid4(), condition_uuid=owner, name="Slowed",
        category=ConditionCategory.CONDITION, behavior_id="condition.spell.slow",
        resulting_max_hp=None, resulting_ac=None)
    appearance = resolve_condition_appearance((fact,), data.condition_recipes, data.condition_media)
    assert not appearance.unsupported
    assert len([layer for layer in appearance.layers if not layer.layer.markerGroup]) == 2
    assert {layer.layer.assetId for layer in appearance.layers if not layer.layer.markerGroup} == {"control.slow.back", "control.slow.front"}
    assert [layer.layer.markerGroup for layer in appearance.layers if layer.layer.markerGroup] == ["slow"]
    record = ConditionMediaLifetime(actor, owner, "condition.spell.slow", applied_ms=0)

    def samples(at, visible=appearance, lifetime=record):
        layers = sample_condition_lifetimes({str(actor): visible}, {owner: lifetime}, data, at)[str(actor)].layers
        return tuple(sample for layer in layers if not layer.layer.markerGroup
                     for sample in sample_condition_media(data, layer))

    assert all(sample.frame == 127 for sample in samples(3999))
    assert all(sample.frame == 0 for sample in samples(4000))
    assert all(sample.alpha == 1 for sample in samples(4000, lifetime=replace(record, applied_ms=None)))
    removed = replace(record, removed_ms=5000,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    tail = samples(5275, ConditionAppearance(), removed)
    assert len(tail) == 2
    assert all(sample.frame == 40 and sample.alpha == pytest.approx(.5) for sample in tail)
    assert not samples(5550, ConditionAppearance(), removed)
    assert not sample_condition_lifetimes({str(actor): ConditionAppearance()}, {owner: removed}, data, 5550)[str(actor)].layers
