"""The imported equipment gesture preserves old gear until body settlement.

These are pure sampling and real actor-pixel boundaries. The separate mixed
playback test owns public equipment mutation, causal intake and map composition.
"""

from dataclasses import replace
from uuid import UUID

import pygame
import pytest

from dnd.blocks.appearance import AppearanceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.life_types import LifeState
from dnd.runtime_reset import reset_engine_runtime
from game.animation import (
    ActorContact, BodySample, EquipmentTimeline, compile_equipment,
    sample_equipment, sample_idle_body,
)
from game.animation_data import DATA_ROOT, load_animation_data, resolve_actor_layers
from game.animation_draw import BodyRows, actor_draw_commands, load_actor_media
from game.animation_types import AnimationData, RigLayer
from game.projection import Camera


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(DATA_ROOT.parent / "rigs/goblin01.json",))


@pytest.fixture(scope="module")
def timeline(data: AnimationData) -> EquipmentTimeline:
    return compile_equipment(data, "incoming-shortsword", ActorContact(
        "actor", (1, 1), "S", 0.5, elevation_steps=1,
    ))


def test_original_equipment_body_timing_and_replay(timeline: EquipmentTimeline) -> None:
    assert (timeline.recipe.bodyClip, timeline.recipe.bodyPlaybackSpeed,
            timeline.recipe.commitFrame, timeline.recipe.media) == ("Taunt", 3, 4, ())
    assert timeline.complete_ms == pytest.approx(388.8888888889)
    stance_frame_ms = 1000 / 9
    stance = sample_equipment(timeline, stance_frame_ms)
    assert stance.body == BodySample("actor", "Taunt", 4, "S")
    assert not stance.complete
    before_end = sample_equipment(timeline, timeline.complete_ms - 0.001)
    assert before_end.body.clip == "Taunt" and not before_end.complete
    complete = sample_equipment(timeline, timeline.complete_ms)
    assert complete.body == BodySample("actor", "Idle", 0, "S")
    assert complete.complete
    later = sample_equipment(timeline, timeline.complete_ms + 250)
    assert later.body == BodySample("actor", "Idle", 3, "S") and later.complete
    reset_engine_runtime(grid_size=(2, 2))
    assert sample_equipment(timeline, stance_frame_ms) == stance
    assert sample_equipment(timeline, timeline.complete_ms + 250) == later


def test_disabled_equipment_body_settles_immediately(data: AnimationData, timeline: EquipmentTimeline) -> None:
    disabled = replace(data, equipment_context=data.equipment_context.model_copy(update={"bodyEnabled": False}))
    direct = compile_equipment(disabled, timeline.root_event_uuid, timeline.actor)
    assert direct.complete_ms == 0
    sample = sample_equipment(direct, 0)
    assert sample.complete and sample.body == BodySample("actor", "Idle", 0, "S")


def test_other_actor_keeps_existing_idle_or_final_death_pose(data: AnimationData) -> None:
    contact = ActorContact("recipient", (2, 1), "NW", 0.82, rig_id="smallscale.goblin01")
    assert sample_idle_body(data, contact, 250) == BodySample("recipient", "Idle", 3, "NW")
    dead = replace(contact, life_state=LifeState.DEAD)
    assert sample_idle_body(data, dead, 0) == BodySample("recipient", "Die", 14, "NW")
    assert sample_idle_body(data, dead, 5000) == sample_idle_body(data, dead, 0)


@pytest.fixture(scope="module")
def screen():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        try:
            yield pygame.display.set_mode((500, 400))
        finally:
            pygame.quit()


@pytest.fixture(scope="module")
def actor_media(screen, timeline: EquipmentTimeline):
    data, actor = timeline.data, timeline.actor
    items = tuple(build_authored_item(name, UUID(int=812)).to_item_presentation_state()
                  for name in ("weapon.dagger", "weapon.shortsword"))
    appearances = tuple(resolve_actor_layers(
        data, AppearanceConfig(body_category="NakedBody", has_beard=False), items,
        ((WeaponSlot.MELEE_MAIN.value, item.item_uuid),), WeaponSet.MELEE, rig_id=data.root_rig,
    ) for item in items)
    rows = load_actor_media(data, tuple((actor, layers, ("Taunt", "Idle")) for layers in appearances))
    return appearances[0], appearances[1], rows


def _pixels(screen: pygame.Surface, timeline: EquipmentTimeline, body: BodySample,
            layers: tuple[RigLayer, ...], rows: BodyRows, quadrant: int) -> bytes:
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus(
        timeline.actor.grid, elevation_steps=timeline.actor.elevation_steps,
    )
    screen.fill((0, 0, 0))
    for _, image, destination, blend, _ in sorted(actor_draw_commands(
        timeline.data, body, timeline.actor, layers, rows, camera,
    ), key=lambda command: command[0]):
        screen.blit(image, destination, special_flags=blend)
    return pygame.image.tobytes(screen, "RGB")


@pytest.mark.parametrize("quadrant", range(4))
def test_real_replacement_layers_draw_and_seek_without_mutating_media(
    screen, timeline: EquipmentTimeline, actor_media, quadrant: int,
) -> None:
    old, new, rows = actor_media
    assert next(layer.category for layer in old if layer.slot == "weapon") == "Melee1"
    assert next(layer.category for layer in new if layer.slot == "weapon") == "Melee3"
    stance = sample_equipment(timeline, 1000 / 9)
    complete = sample_equipment(timeline, timeline.complete_ms)
    retained = _pixels(screen, timeline, stance.body, new if stance.complete else old, rows, quadrant)
    assert retained != _pixels(screen, timeline, stance.body, new, rows, quadrant)
    settled = _pixels(screen, timeline, complete.body, new if complete.complete else old, rows, quadrant)
    assert settled != _pixels(screen, timeline, complete.body, old, rows, quadrant)
    assert retained == _pixels(screen, timeline, stance.body, old, rows, quadrant)
