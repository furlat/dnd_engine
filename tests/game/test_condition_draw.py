"""Condition filters preserve authored layer scope, hit priority and actor alpha."""

import pygame
import pytest

from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands
from game.animation_types import RigLayer
from game.condition_animation import ConditionAppearance
from game.condition_types import ConditionBodyColor
from game.projection import Camera, TILE_WIDTH


@pytest.fixture(scope="module")
def actor_pixels():
    data = load_animation_data()
    rig = data.rigs["neuroclient.modular"]
    contact = ActorContact("actor", (0, 0), "S", data.rig.TILE_W / TILE_WIDTH)
    layers = tuple(RigLayer(slot, "Head5" if slot == "helmet" else slot,
                            alpha=.5 if slot == "shadow" else 1) for slot in rig.slot_order)
    rows = {}
    positions = {}
    for index, layer in enumerate(layers):
        image = pygame.Surface((rig.cell_width, rig.cell_height), pygame.SRCALPHA)
        positions[layer.slot] = (index + 2, 2)
        image.set_at(positions[layer.slot], (180, 60, 30, 255))
        rows[contact.rig_id, "Idle", layer.category, rig.facing_rows["S"]] = image
    return data, contact, layers, rows, positions


@pytest.mark.parametrize("flash", (None, 0x00FF00))
def test_source_body_filter_slots_flash_priority_and_whole_actor_alpha(actor_pixels, flash) -> None:
    data, contact, layers, rows, positions = actor_pixels
    condition = ConditionAppearance(alpha=.5, body_color=ConditionBodyColor(
        tintRgb=0x80FF40, saturation=.5, brightness=1.2,
    ))
    commands = actor_draw_commands(data, BodySample("actor", "Idle", 0, "S"), contact,
        layers, rows, Camera(zoom=1), flash=flash, condition=condition)
    images = {command[4][6]: command[1] for command in commands}
    body = images["actor"]
    # Pixi's exact matrix: tint @ saturate(-.5) @ brightness(1.2).
    # (180,60,30) -> (135,75,60) -> (81.3176,90,18.0706).
    filtered = (81, 90, 18) if flash is None else (0, 60, 0)
    for slot in ("body", "shoes", "legs", "mount", "chest", "belt", "hands",
                 "offhand", "weapon", "weaponGlow", "backpack", "head", "beard", "helmet"):
        assert tuple(body.get_at(positions[slot])) == (*filtered, 255), slot
    for slot in ("aura", "slash", "effect", "effect2", "effect3"):
        expected = (180, 60, 30) if flash is None else (0, 60, 0)
        assert tuple(body.get_at(positions[slot])) == (*expected, 255), slot
    shadow = images["actor_shadow"]
    assert tuple(shadow.get_at(positions["shadow"])) == (180, 60, 30, 128)
    assert body.get_alpha() == shadow.get_alpha() == 128
    composed = pygame.Surface(body.get_size(), pygame.SRCALPHA)
    composed.blit(shadow, (0, 0))
    assert composed.get_at(positions["shadow"]).a == 64
    composed.blit(body, (0, 0))
    assert composed.get_at(positions["body"]).a == 128
    # Preloaded rows remain reusable after both condition and hit-flash frames.
    for layer in layers:
        source = rows[contact.rig_id, "Idle", layer.category, data.rigs[contact.rig_id].facing_rows["S"]]
        assert tuple(source.get_at(positions[layer.slot])) == (180, 60, 30, 255)
