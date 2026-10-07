"""Received item properties color existing pixels across real transfer replay."""
from dataclasses import replace
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.core.creature_types import DamageType
from dnd.core.item_types import ItemEffectPresentationState
from game.animation import BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands
from game.item_appearance import item_source_palettes
from game.item_draw import item_ground_commands
from game.item_effects import item_material
from dnd.player.reduction import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from tests.game.item_appearance_scenarios import item_transfer_history
from tests.game.player_helpers import player_history


@pytest.fixture
def display(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((600, 400))
    yield
    pygame.quit()


def effect(kind, behavior="item.property.additional_damage"):
    identity = uuid4()
    return ItemEffectPresentationState(effect_uuid=identity, contribution_uuid=identity,
                                       behavior_id=behavior, damage_type=kind)


def test_material_precedence_unknown_effect_and_source_alpha(display):
    source = pygame.Surface((8, 8), pygame.SRCALPHA)
    color = item_source_palettes()["Melee1"][0]
    source.fill((color >> 16 & 255, color >> 8 & 255, color & 255, 173), (2, 2, 4, 4))
    source.set_at((0, 0), (60, 30, 10, 45))  # Unmatched source shadow/material.
    psychic = effect(DamageType.PSYCHIC)
    poison = effect(DamageType.POISON, "condition.consumable.weapon_coat.basic_poison")
    draw = lambda effects: item_material(source, effects, "weapon", {}, category="Melee1", base_tint=0x334455)
    poisoned = draw((psychic, poison))
    assert pygame.image.tobytes(poisoned, "RGBA") == pygame.image.tobytes(draw((poison, psychic)), "RGBA")
    assert pygame.image.tobytes(poisoned, "RGBA") == pygame.image.tobytes(draw((poison,)), "RGBA")
    unknown = effect(DamageType.FIRE, "unknown.effect")
    assert pygame.image.tobytes(draw((unknown,)), "RGBA") == pygame.image.tobytes(draw(()), "RGBA")
    assert np.array_equal(pygame.surfarray.array_alpha(poisoned), pygame.surfarray.array_alpha(source))
    assert poisoned.get_at((0, 0)) == source.get_at((0, 0))
    assert poisoned.get_at((3, 3)).g > poisoned.get_at((3, 3)).r
    assert draw((psychic,)).get_at((3, 3)).b > draw((psychic,)).get_at((3, 3)).g


@pytest.mark.parametrize("weapon,coat,persistent", [
    ("weapon.roster.psychic_scimitar", None, True),
    ("weapon.roster.psychic_greataxe", None, True),
    ("weapon.roster.psychic_trident", None, True),
    ("weapon.roster.psychic_longsword", None, True),
    ("weapon.roster.psychic_longsword_greater", None, True),
    ("weapon.roster.ember_longsword", None, True),
    ("weapon.roster.ember_greatsword", None, True),
    ("weapon.longsword", "consumable.weapon_coat.basic_poison", False),
])
def test_native_material_survives_floor_and_recipient_then_obeys_expiry(display, weapon, coat, persistent):
    original, recipient, identity, recorded, _ = item_transfer_history(
        include_floor_robe=False, weapon_item_id=weapon, coating_item_id=coat)
    state, roots = player_history(recorded, role="holder")
    data = load_animation_data()
    rows, seen = {}, set()
    for root in (None, *roots):
        if root is not None:
            state = reduce_lineage(state, root)
        actors = scene_actors(state, data, {})
        media = load_scene_media(actors, data, body_rows=rows)
        for actor in actors:
            item_layer = next((layer for layer in actor.layers if layer.item_uuid == identity and layer.item_effects), None)
            if item_layer is None or (actor.contact.actor_uuid, item_layer.slot) in seen:
                continue
            plain = tuple(replace(layer, item_effects=()) if layer.item_uuid == identity else layer for layer in actor.layers)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(600, 400))
                body = BodySample(actor.contact.actor_uuid, "Idle", 0, actor.contact.facing)
                actual = actor_draw_commands(data, body, actor.contact, actor.layers, media, camera)
                ordinary = actor_draw_commands(data, body, actor.contact, plain, media, camera)
                assert any(not np.array_equal(pygame.surfarray.array3d(a.surface), pygame.surfarray.array3d(b.surface)) for a, b in zip(actual, ordinary))
                assert all(np.array_equal(pygame.surfarray.array_alpha(a.surface), pygame.surfarray.array_alpha(b.surface)) for a, b in zip(actual, ordinary))
            seen.add(actor.contact.actor_uuid)
            seen.add((actor.contact.actor_uuid, item_layer.slot))
        if identity in state.objects and "floor" not in seen:
            obj = state.objects[identity]
            plain_obj = replace(obj, item=replace(obj.item, item_effects=()))
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(600, 400))
                actual = item_ground_commands(obj, camera)
                ordinary = item_ground_commands(plain_obj, camera)
                assert actual[0].surface is ordinary[0].surface or pygame.image.tobytes(actual[0].surface, "RGBA") == pygame.image.tobytes(ordinary[0].surface, "RGBA")
                assert not np.array_equal(pygame.surfarray.array3d(actual[-1].surface), pygame.surfarray.array3d(ordinary[-1].surface))
                assert actual[-1].destination == ordinary[-1].destination
            seen.add("floor")
    assert {str(original), str(recipient), "floor"} <= seen
    assert identity not in state.objects
    held = next(layer for layer in state.actors[recipient].visual_loadout.layers if layer.item_uuid == identity)
    assert bool(held.item_effects) == persistent
