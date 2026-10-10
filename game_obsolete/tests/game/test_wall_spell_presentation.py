"""Real ordered wall casts survive cold replay and select delivered native views."""

import pygame
import pytest
from math import floor, hypot

from dnd.core.events import EventQueue
from dnd.core.presentation_geometry import WallPresentationGeometry, WallRing, WallSegment
from game.animation_data import load_animation_data
from game.authoring_conversion import validate_wall_modules
from game.choreography import bind_choreography, sample_choreography
from dnd.player.facts import DamageFact, SpellFact
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, project_screen
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.wall_media import wall_module_centers
from game.wall_profile import wall_media_limitation
from tests.game.wall_spell_scenarios import wall_spell_history


@pytest.fixture(scope="module")
def wall_data():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("axis,raised", (("x", False), ("y", False), ("x", True), ("diagonal", False), ("oblique", False)))
def test_native_wall_formation_hold_damage_and_clear_survive_cold_replay(wall_data, axis, raised):
    recorded = wall_spell_history(axis=axis, raised=raised)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views["caster"])))
    assert EventQueue.event_cursor() == 0
    cast = next(lineage for lineage in lineages if isinstance(lineage.root.fact, SpellFact)
                and lineage.root.fact.behavior_id == "spell.wall_of_fire")
    for lineage in lineages:
        if lineage is cast:
            break
        state = reduce_lineage(state, lineage)
    before = state
    group = bind_choreography(before, cast, wall_data)
    assert not group.gaps, group.gaps
    assert len(group.body_actions) == 1 and not group.nodes, "Only the maintained field owns formation"
    assert not spatial_media_draw_commands(before, wall_data, 0, Camera())
    assert not spatial_media_draw_commands(sample_choreography(group, 0).displayed, wall_data, 0, Camera())
    lifetimes = register_spatial_lifetimes({}, before, wall_data, absolute_start_ms=0,
                                          lineage=cast, choreography=group)
    identity, lifetime = next(iter(lifetimes.items()))
    assert lifetime.applied_ms is not None
    assert group.after.senses is not None
    effect = group.after.senses.spatial_effects[identity]
    geometry = effect.area_geometry
    assert isinstance(geometry, WallPresentationGeometry)
    assert geometry.base_height_steps == (2 if raised else 0)
    start = lifetime.applied_ms
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=(640, 480)).with_focus((6, 6))
        assert not spatial_media_draw_commands(group.after, wall_data, start + 100, camera, lifetimes=lifetimes)
        for age, phase in ((500, "apply"), (1600, "hold"), (3600, "hold")):
            commands = spatial_media_draw_commands(group.after, wall_data, start + age, camera, lifetimes=lifetimes)
            assert commands, (axis, raised, quadrant, age)
            assert {(floor(row.evidence[1][0]+.5), floor(row.evidence[1][1]+.5)) for row in commands} <= set(effect.positions)
            assert all(row.evidence[6] == "spatial_media" for row in commands)
            bank_marker = {"x": "_d0_", "y": "_d1_", "diagonal": "_pp_", "oblique": "_pp_"}[axis]
            assert all(bank_marker in row.evidence[2] for row in commands)
            if axis == "diagonal":
                assert {"_v0.", "_v1."} <= {marker for row in commands
                    for marker in ("_v0.", "_v1.") if marker in row.evidence[2]}, \
                    "Diagonal modules must use both delivered flame layouts"
            assert all(row.evidence[2].endswith(phase) and row.support_height_steps == geometry.base_height_steps
                       for row in commands)
            assert any(row.surface.get_bounding_rect().width for row in commands)
            # Every view samples its declared crop about the unchanged native pivot.
            row = commands[0]
            asset = wall_data.projectile_assets[row.evidence[2]]
            facing = ("E", "S", "W", "N")[quadrant]
            storage = wall_data.projectile_storage[asset.assetId].phases["impact"].layers[0]
            part = storage.partsByFacing[facing][row.evidence[9]][0]
            anchor = project_screen(row.evidence[1], camera, elevation_steps=geometry.base_height_steps)
            assert row.destination == (round(anchor[0] + part.offset[0] - asset.anchor.x * asset.frame.width),
                                       round(anchor[1] + part.offset[1] - asset.anchor.y * asset.frame.height))
        first = spatial_media_draw_commands(group.after, wall_data, start + 1600, camera, lifetimes=lifetimes)
        repeated = spatial_media_draw_commands(group.after, wall_data, start + 3600, camera, lifetimes=lifetimes)
        assert [(row.destination, row.evidence, pygame.image.tobytes(row.surface, "RGBA")) for row in first] == [
            (row.destination, row.evidence, pygame.image.tobytes(row.surface, "RGBA")) for row in repeated]
    if axis in {"x", "y"}:
        assert any(isinstance(node.fact, DamageFact) and node.fact.stage == "applied"
                   for lineage in lineages for node in lineage.events), "Native wall exposure produces damage"
    heat = [node.fact.spatial_source for lineage in lineages for node in lineage.events
            if isinstance(node.fact, DamageFact) and node.fact.stage == "applied"
            and node.fact.spatial_source is not None and node.fact.spatial_source.exposure == "radiated_heat"]
    if axis in {"x", "y"}:
        assert heat, "Cardinal fixtures exercise actual native heat exposure"
    assert all(source.spatial_effect_uuid == identity and source.position in effect.positions for source in heat)
    assert all(source.target_position != source.position and source.base_height_steps == geometry.base_height_steps
               for source in heat), "Recorded hot-side exposure retains both physical contacts"
    state = before
    now = 0.
    retained = {}
    for lineage in lineages:
        bound = bind_choreography(state, lineage, wall_data)
        retained = register_spatial_lifetimes(retained, state, wall_data, absolute_start_ms=now,
                                              lineage=lineage, choreography=bound)
        state = reduce_lineage(state, lineage)
        now += bound.complete_ms
    removal = retained[identity].removed_ms
    assert removal is not None and state.senses is not None and identity not in state.senses.spatial_effects
    assert spatial_media_draw_commands(state, wall_data, removal + 200, Camera(), lifetimes=retained)
    assert not spatial_media_draw_commands(state, wall_data, removal + 650, Camera(), lifetimes=retained)
    assert EventQueue.event_cursor() == 0, "No native engine state is consulted during playback"


@pytest.mark.parametrize("path,message", ((WallRing(center=(6, 6), radius_feet=10), "Curved"),
    (WallSegment(start=(4, 4), end=(8, 8)), "Diagonal")))
def test_missing_wall_forms_are_explicit_instead_of_substituting_media(path, message):
    geometry = WallPresentationGeometry(path=path, base_height_steps=0, width_feet=1, height_feet=20)
    assert message in wall_media_limitation(geometry)


def test_wall_initialization_rejects_missing_alternate_media_and_excess_hold(wall_data):
    binding = wall_data.spatial_media["spatial_effect.spell.wall_of_fire"]
    alternate = binding.layers[0].wallAxes[1].variants[1].applicationAssetId
    incomplete = {identity: asset for identity, asset in wall_data.projectile_assets.items()
                  if identity != alternate}
    with pytest.raises(ValueError, match="lacks registered media"):
        validate_wall_modules(binding, incomplete, wall_data.projectile_storage)
    with pytest.raises(ValueError, match="hold exceeds delivered frames"):
        validate_wall_modules(binding.model_copy(update={"holdFrames": 65}),
                              wall_data.projectile_assets, wall_data.projectile_storage)
    front = binding.layers[1].model_copy(update={"wallAxes": tuple(reversed(binding.layers[1].wallAxes))})
    with pytest.raises(ValueError, match="paired wall layers"):
        validate_wall_modules(binding.model_copy(update={"layers": (binding.layers[0], front)}),
                              wall_data.projectile_assets, wall_data.projectile_storage)


def test_disclosed_wall_arc_is_continuous_reversible_and_does_not_bridge_hidden_cells():
    path = WallSegment(start=(4, 4), end=(8, 8))
    cells = {(x, y) for x in range(4, 9) for y in range(4, 9)}
    points = wall_module_centers(path, cells, .75)
    assert points[0] == path.start and points[-1] == path.end
    assert all(hypot(b[0]-a[0], b[1]-a[1]) <= .75 for a, b in zip(points, points[1:]))
    reverse = WallSegment(start=path.end, end=path.start)
    assert wall_module_centers(reverse, cells, .75) == points
    disclosed = cells - {(6, 6)}
    hidden = wall_module_centers(path, disclosed, .75)
    assert 0 < len(hidden) < len(points)
    assert hidden == tuple(point for point in points
                           if (floor(point[0]+.5), floor(point[1]+.5)) in disclosed)


@pytest.mark.parametrize("side", ("inside", "outside"))
def test_native_ring_replay_admits_complete_shell_without_revealing_partial_views(wall_data, side):
    recorded = wall_spell_history(ring_hot_side=side)
    for role in ("center", "caster"):
        state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views[role])))
        for lineage in lineages:
            bound = bind_choreography(state, lineage, wall_data)
            if any(isinstance(event.fact, SpellFact) and event.fact.behavior_id == "spell.wall_of_fire"
                   for event in lineage.events):
                assert bound.after.senses is not None
                identity, effect = next(iter(bound.after.senses.spatial_effects.items()))
                assert isinstance(effect.area_geometry, WallPresentationGeometry)
                assert isinstance(effect.area_geometry.path, WallRing)
                assert effect.area_geometry.path.radius_feet == 10
                lifetimes = register_spatial_lifetimes({}, state, wall_data, absolute_start_ms=0,
                    lineage=lineage, choreography=bound)
                start = lifetimes[identity].applied_ms
                assert start is not None
                for quadrant in range(4):
                    commands = spatial_media_draw_commands(bound.after, wall_data, start+1600,
                        Camera(quadrant=quadrant), lifetimes=lifetimes)
                    ring = [row for row in commands if "wall_ring_matched" in str(row.evidence[2])]
                    assert bool(ring) == (role == "center")
                if role == "center":
                    assert not bound.gaps
                else:
                    assert any("complete disclosed" in message for _, message in bound.gaps)
                break
            state = reduce_lineage(state, lineage)
        else:
            pytest.fail("Actual ring cast missing from observer packets")
