"""Permanent native point-light owners remain visible and retire independently."""

from dataclasses import replace
from types import MappingProxyType

import pygame
import pytest

from game.animation_data import load_animation_data
from game.maintained_media import maintained_media_frame, maintained_media_alpha
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_field_media import field_media_commands
from tests.game.continual_flame_scenarios import continual_flame_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("observer", ("caster", "recipient"))
def test_two_native_anchors_are_disclosed_drawn_and_retire_independently(data, observer):
    history = continual_flame_history()
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
    counts = []
    for root in roots:
        before = reduce_lineage(before, root)
        assert before.senses is not None
        effects = {owner: effect for owner, effect in before.senses.spatial_effects.items()
            if effect.content_ref.content_id == "spatial_effect.spell.continual_flame"}
        counts.append(len(effects))
        for effect in effects.values():
            assert len(effect.positions) == 1 and effect.anchor_position in effect.positions
            assert effect.area_geometry is None
        for quadrant in range(4):
            commands = spatial_media_draw_commands(before, data, 2000, Camera(quadrant=quadrant))
            assert {command.key[-1][0] for command in commands} == {str(owner) for owner in effects}
            assert all(pygame.surfarray.array_alpha(command.surface).any() for command in commands)
    assert 2 in counts
    last_pair = max(index for index, count in enumerate(counts) if count == 2)
    assert 1 in counts[last_pair + 1:] and counts[-1] == 0


def test_point_clump_requires_received_anchor_and_current_supported_visibility(data):
    history = continual_flame_history()
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["caster"])))
    for root in roots:
        state = reduce_lineage(state, root)
        if state.senses is not None and state.senses.spatial_effects:
            break
    assert state.senses is not None
    owner, effect = next(iter(state.senses.spatial_effects.items()))
    binding = data.spatial_media[effect.content_ref.content_id]
    layer = binding.layers[0]
    assert effect.area_geometry is None and effect.anchor_position is not None
    camera = Camera()

    def draw(current, selected=layer, anchor=effect.anchor_position):
        return field_media_commands(current, data, owner, None, effect.positions,
            binding, selected, 0, layer.assetId, 0, camera, 1, anchor_position=anchor)

    assert draw(state)
    assert not draw(state, anchor=None)
    hidden = replace(state, senses=replace(state.senses,
        visible=tuple(cell for cell in state.senses.visible if cell != effect.anchor_position)))
    assert not draw(hidden)
    unsupported = replace(state, tiles=MappingProxyType({cell: tile for cell, tile in state.tiles.items()
        if cell != effect.anchor_position}))
    assert not draw(unsupported)
    for composition in ("floor", "xy_volume", "xyz_volume", "wall_modules"):
        # This boundary accepts only point clumps. No fabricated volume/wall geometry.
        assert not draw(state, layer.model_copy(update={"composition": composition}))


def test_permanent_hold_uses_fixed_registered_clock_and_continues_during_retirement(data):
    binding = data.spatial_media["spatial_effect.spell.continual_flame"]
    for layer in binding.layers:
        assert maintained_media_frame(data, binding, layer, 0, 0) == (layer.applicationAssetId, 0)
        assert maintained_media_frame(data, binding, layer, 1499, 0) == (layer.applicationAssetId, 47)
        assert maintained_media_frame(data, binding, layer, 1500, 0) == (layer.assetId, 0)
        assert maintained_media_frame(data, binding, layer, 3499, 0) == (layer.assetId, 63)
        assert maintained_media_frame(data, binding, layer, 3500, 0) == (layer.assetId, 0)
        reacquired = maintained_media_frame(data, binding, layer, 4000, None)
        assert reacquired is not None and reacquired[0] == layer.assetId
        assert maintained_media_alpha(binding, layer, 5200, 5000) == pytest.approx(.5)
        assert maintained_media_alpha(binding, layer, 5400, 5000) == 0
