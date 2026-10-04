"""Accepted gap artwork follows native recipients, geometry and finite clocks."""

from math import atan2, cos, hypot, pi, sin

import numpy as np
import pygame
import pytest

from dnd.core.presentation_geometry import ConePresentationGeometry, WallAssemblyPresentationGeometry, WallRing
from dnd.core.wall_geometry import wall_shell_cells
from game.animation import facing_vector, sample_cast, view_facing
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.area_media import AreaMedia
from game.attack import BoundAttack, attack_projectile_contact, project_attack_projectile, sample_attack
from game.cast_media import cast_media_draw_commands, cast_media_placement, sample_cast_body_materials
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import choreography_draw_commands, load_choreography_media
from game.combat import BoundCast
from game.condition_draw import condition_body_ramp
from game.directed_media import directed_draw_commands
from game.draw_commands import DrawCommand
from game.player_facts import AttackFact
from game.player_reduction import reduce_lineage
from game.projection import Camera, project_screen, project_world
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.wall_assembly_media import assembly_media_draw_commands, assembly_media_limitation
from game.volume_media import ExcludedSphere, compose_volume
from game.thorns_surface import thorns_commands, vine_mesh
from tests.game.player_helpers import player_history
from tests.game.production_gap_scenarios import (
    CONE_DIRECTIONS, call_lightning_gap_history, cone_gap_history,
    thorns_ring_history, wind_interception_history,
)


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def _pixels(commands: tuple[DrawCommand, ...]):
    return tuple((row.destination, pygame.image.tobytes(row.surface, "RGBA")) for row in commands)


@pytest.mark.parametrize("heading,oblique", [*((heading, False) for heading in range(8)), (0, True)])
def test_cone_uses_actual_direction_and_ground_apex_in_every_camera(data: AnimationData, heading, oblique):
    history = cone_gap_history(heading=heading, oblique=oblique)
    state, roots = player_history(history, role="caster")
    initial_hp = {actor.name: actor.normal_hp for actor in state.actors.values()}
    casts = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        casts.extend(node.bound for node in group.nodes if isinstance(node.bound, BoundCast))
        state = reduce_lineage(state, root)
    bound, = casts
    timeline = bound.timeline
    geometry = timeline.source.area_geometry
    assert isinstance(geometry, ConePresentationGeometry)
    dx, dy = (2, 1) if oblique else CONE_DIRECTIONS[heading]
    gx, gy = geometry.direction
    assert gx*dy == gy*dx and gx*dx+gy*dy > 0
    assert geometry.origin == (14, 14) and geometry.length_feet == 60 and geometry.angle_degrees == 53
    assert len(timeline.applications) == 2
    losses = {actor.name: initial_hp[actor.name]-actor.normal_hp for actor in state.actors.values()}
    assert losses["Caster"] == losses["Outside"] == 0
    assert losses["Recipient"] == 32 and losses["Saved"] == 16
    assert all(row.damage_start_ms is None or row.damage_start_ms >= row.travel_end_ms
               for row in timeline.applications)
    for application in timeline.applications:
        recipient = application.source.target.actor_uuid
        assert recipient not in dict(sample_cast_body_materials(timeline, application.travel_end_ms-1))
        material = dict(sample_cast_body_materials(timeline, application.travel_end_ms+100))[recipient]
        assert material.strength > 0
        assert recipient not in dict(sample_cast_body_materials(timeline, application.travel_end_ms+751))
    field_tracks = {track.id for track in timeline.recipe.media if track.attachment == "source_ground"}
    assert field_tracks
    area = AreaMedia(bound.area_boundaries, bound.area_solids, bound.area_supports,
        admitted=timeline.source.resolved_area_positions)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus((14, 14))
        for track in timeline.recipe.media:
            if track.id not in field_tracks:
                continue
            placement = cast_media_placement(timeline, track, timeline.source.caster, camera)
            assert placement.anchor == project_screen((14, 14), camera)
            rotation = atan2(sin(placement.rotation), cos(placement.rotation))
            if not oblique:
                assert rotation == pytest.approx(0, abs=1e-10)
            else:
                assert 0 < abs(rotation) < pi/4
            bx, by = facing_vector(view_facing(timeline.facing, quadrant, data), data)
            rotated = (bx*cos(rotation)-by*sin(rotation), bx*sin(rotation)+by*cos(rotation))
            start = project_world(geometry.origin, quadrant=quadrant)
            end = project_world((geometry.origin[0]+gx, geometry.origin[1]+gy), quadrant=quadrant)
            aimed = (end[0]-start[0], end[1]-start[1])
            assert tuple(value/hypot(*rotated) for value in rotated) == pytest.approx(
                tuple(value/hypot(*aimed) for value in aimed), abs=1e-10)
        at = timeline.release_ms+500
        commands = cast_media_draw_commands(timeline, sample_cast(timeline, at), camera, area, {})
        field = tuple(command for command in commands if command.evidence[8] in field_tracks)
        assert field and all(command.surface.get_bounding_rect() for command in field)
        assert {command.evidence[1] for command in field} == {(14, 14)}
        # Delivered near/middle/far depths must remain distinct in the shared
        # painter; ground is a separate plane, never a recipient-centered cone.
        airborne = [command for command in field if command.area is None or command.key[0] != 0]
        assert len({command.key[1] for command in airborne}) >= 3
        assert _pixels(commands) == _pixels(cast_media_draw_commands(
            timeline, sample_cast(timeline, at), camera, area, {}))
        assert not cast_media_draw_commands(timeline, sample_cast(timeline, timeline.complete_ms+1), camera, area, {})


@pytest.mark.parametrize("moved_empty_repeat", [False, True])
def test_call_v5_has_one_selected_ground_strike_for_initial_and_retained_repeat(data: AnimationData, moved_empty_repeat):
    state, roots = player_history(call_lightning_gap_history(moved_empty_repeat=moved_empty_repeat), role="caster")
    casts = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        casts.extend(node.bound for node in group.nodes if isinstance(node.bound, BoundCast)
            and node.bound.timeline.recipe.definitionRef.content_id == "spell.call_lightning")
        state = reduce_lineage(state, root)
    assert len(casts) == 2
    for index, bound in enumerate(casts):
        timeline = bound.timeline
        repeated_empty = moved_empty_repeat and index == 1
        expected_ground = (9, 8) if repeated_empty else (7, 5)
        assert timeline.source.caster.grid == ((3, 6) if repeated_empty else (3, 5))
        ground = timeline.ground_delivery
        assert ground is not None and ground.target.grid == expected_ground
        assert ground.travel_end_ms == pytest.approx(timeline.release_ms+31.25)
        assert len(timeline.applications) == (0 if repeated_empty else 3)
        assert all(row.travel_end_ms == ground.travel_end_ms for row in timeline.applications)
        assert all(row.damage_start_ms is None or row.damage_start_ms >= ground.travel_end_ms
                   for row in timeline.applications)
        area = AreaMedia(bound.area_boundaries, bound.area_solids, bound.area_supports,
            admitted=timeline.source.resolved_area_positions)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=.5).with_focus((7, 5))
            at = timeline.release_ms+250
            commands = cast_media_draw_commands(timeline, sample_cast(timeline, at), camera, area, {})
            assert commands and {command.evidence[1] for command in commands} == {expected_ground}
            assert directed_draw_commands(timeline, sample_cast(timeline, at), camera, area)
            assert not cast_media_draw_commands(timeline, sample_cast(timeline, timeline.complete_ms+1), camera, area, {})
            assert not directed_draw_commands(timeline, sample_cast(timeline, timeline.complete_ms+1), camera, area)
    assert not any(condition.name == "Concentrating" for actor in state.actors.values()
                   if actor.name == "Caster" for condition in actor.conditions)


@pytest.mark.parametrize("direction,blocked", [
    ((0, 1), True), ((1, 1), True), ((1, 2), True), ((0, 1), False),
])
def test_wind_stops_native_bow_at_received_intersection_and_finishes_gust(data: AnimationData, direction, blocked):
    state, roots = player_history(wind_interception_history(direction=direction, blocked=blocked), role="archer")
    before_hp = next(actor.normal_hp for actor in state.actors.values() if actor.name == "Recipient")
    selected = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        selected.extend((group, node, root) for node in group.nodes if isinstance(node.bound, BoundAttack))
        state = reduce_lineage(state, root)
    assert len(selected) == 1
    group, node, root = selected[0]
    assert isinstance(node.bound, BoundAttack)
    timeline = node.bound.timeline
    projectile = timeline.projectile
    assert projectile is not None
    assert (next(actor.normal_hp for actor in state.actors.values() if actor.name == "Recipient") == before_hp) is blocked
    if not blocked:
        assert projectile.interception is None
        flight = sample_attack(timeline, projectile.end_ms-1e-4)
        assert flight.projectiles
        for quadrant in range(4):
            endpoint = project_attack_projectile(timeline, flight.projectiles[0], quadrant)
            point, _ = attack_projectile_contact(timeline, endpoint, quadrant)
            assert hypot(point[0]-timeline.target.grid[0], point[1]-timeline.target.grid[1]) < .75
            assert point[0] > 10, "the clear arrow must pass the wall crossing and reach its recipient"
        return
    interception = projectile.interception
    assert interception is not None
    attack, = (event.fact for event in root.events if isinstance(event.fact, AttackFact))
    assert interception.position == attack.projectile_deflection_position
    assert 0 < interception.fraction < 1
    assert interception.tangent[0]*direction[1] == interception.tangent[1]*direction[0]
    assert not timeline.damage_total
    media = load_choreography_media(group)
    font = pygame.font.Font(None, 16)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus((8, 8))
        flight = sample_attack(timeline, projectile.end_ms-1e-4)
        assert flight.projectiles
        endpoint = project_attack_projectile(timeline, flight.projectiles[0], quadrant)
        point, _ = attack_projectile_contact(timeline, endpoint, quadrant)
        assert point == pytest.approx(interception.position, abs=1e-3)
        def gust(age):
            at = node.start_ms+projectile.end_ms+age
            commands = choreography_draw_commands(group, sample_choreography(group, at), media,
                font, font, camera, include_bodies=False)
            return tuple(row for row in commands if row.owner == timeline.root_event_uuid and row.volume is not None)
        assert not gust(-1)
        present = gust(250)
        assert present and any(row.surface.get_bounding_rect() for row in present)
        assert _pixels(present) == _pixels(gust(250))
        assert not gust(800)


def test_thorns_native_ten_foot_ring_preserves_disclosure_and_real_removal(data: AnimationData):
    state, roots = player_history(thorns_ring_history(), role="caster")
    retained = {}
    clock = 0.
    first = None
    retired = None
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        retained = register_spatial_lifetimes(retained, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group)
        for owner, record in retained.items():
            if record.effect.content_ref.content_id == "spatial_effect.spell.wall_of_thorns":
                if first is None:
                    first = (owner, record)
                if record.removed_ms is not None:
                    retired = record
        state = reduce_lineage(state, root)
        clock += group.complete_ms+500
    assert first is not None and retired is not None
    owner, record = first
    effect = record.effect
    geometry = effect.area_geometry
    assert isinstance(geometry, WallAssemblyPresentationGeometry) and isinstance(geometry.path, WallRing)
    assert geometry.height_feet == 10 and geometry.path.radius_feet == 10 and geometry.width_feet == 5
    assert record.applied_ms is not None and retired.removed_ms is not None
    assert 0 < len(effect.positions) < len(wall_shell_cells(geometry))
    received_cells = frozenset(effect.positions)
    binding = data.spatial_media[effect.content_ref.content_id]
    assert assembly_media_limitation(effect, binding) is None
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus((7, 7))
        def draw(at, removed=None):
            return assembly_media_draw_commands(effect, owner, data, binding, at, camera, record.applied_ms, removed)
        formation = draw(record.applied_ms+700)
        held = draw(record.applied_ms+2700)
        retirement = draw(retired.removed_ms+250, retired.removed_ms)
        assert formation and held and retirement
        assert _pixels(formation) != _pixels(held)
        assert _pixels(held) == _pixels(draw(record.applied_ms+4700))
        assert not draw(retired.removed_ms+1100, retired.removed_ms)
        for command in (*formation, *held, *retirement):
            assert command.owner == str(owner) and command.volume is not None
            volume = command.volume
            image, _ = compose_volume(command.surface, volume, camera, destination=command.destination)
            visible = pygame.surfarray.array_alpha(image) > 0
            assert np.any(visible)
        # The ordinary observer receives original physical sections, not an
        # unknown whole ring or a new ground-cell crop of elevated overhangs.
        registration = binding.layers[0].wallAssembly
        assert registration is not None and registration.thorns is not None
        whole = thorns_commands(geometry, registration.thorns, data, 2700, True, 0,
            camera, None, tuple(range(16)), (), (), (), str(owner), "hold")
        assert whole and _pixels(held) != _pixels(whole)
        hidden = effect.model_copy(update={"positions": ()})
        assert not assembly_media_draw_commands(hidden, owner, data, binding,
            record.applied_ms+2700, camera, record.applied_ms, None)
        masked = assembly_media_draw_commands(effect, owner, data, binding,
            record.applied_ms+2700, camera, record.applied_ms, None,
            exclusions=(ExcludedSphere(provider="received-suppression", center=(7, 7), elevation=1, radius=10, vertical_scale=1),))
        assert masked
        for command in masked:
            assert command.volume is not None
            image, _ = compose_volume(command.surface, command.volume, camera, destination=command.destination)
            assert not image.get_bounding_rect()
    assert frozenset(effect.positions) == received_cells


def test_cone_frost_preserves_original_current_pose_alpha_and_source_pixels(data: AnimationData):
    material = data.drafts["spell.cone_of_cold"].bodyMaterials[0].material
    assert material.texture is not None and material.normalTexture is not None
    noise = pygame.image.load(data.resources[material.texture]).convert_alpha()
    normal = pygame.image.load(data.resources[material.normalTexture]).convert_alpha()
    rig = data.rigs[data.root_rig]
    poses = []
    for clip_name in ("Idle", data.damage_context.bodyClip):
        clip = rig.clips[clip_name]
        sheet = pygame.image.load(data.resources[clip.sheets["NakedBody"]]).convert_alpha()
        pose = sheet.subsurface((0, 0, rig.cell_width, rig.cell_height)).copy()
        original = pygame.image.tobytes(pose, "RGBA")
        treated = condition_body_ramp(pose, material, texture=noise, normal_texture=normal,
            cell_size=(rig.cell_width, rig.cell_height), strength=.33)
        assert np.array_equal(pygame.surfarray.array_alpha(treated), pygame.surfarray.array_alpha(pose))
        assert pygame.image.tobytes(treated, "RGBA") != original
        assert pygame.image.tobytes(pose, "RGBA") == original
        clear = condition_body_ramp(pose, material, texture=noise, normal_texture=normal,
            cell_size=(rig.cell_width, rig.cell_height), strength=0)
        assert pygame.image.tobytes(clear, "RGBA") == original
        poses.append(pygame.surfarray.array_alpha(treated))
    assert not np.array_equal(*poses), "each current source pose retains its own silhouette"


def test_thorns_circular_visibility_selection_keeps_original_module_variants(data: AnimationData):
    binding = data.spatial_media["spatial_effect.spell.wall_of_thorns"]
    registration = binding.layers[0].wallAssembly
    assert registration is not None and registration.thorns is not None
    material = registration.thorns
    resource = data.resources[material.components]
    full = vine_mesh(resource, 16, 16., material.nativeUnitsPerCell, tuple(range(16)), True)
    selected = (3, 7, 12)
    partial = vine_mesh(resource, 16, 16., material.nativeUnitsPerCell, selected, True)
    vertices_per_module = len(full[0])//16
    for slot, original in enumerate(selected):
        source = slice(original*vertices_per_module, (original+1)*vertices_per_module)
        retained = slice(slot*vertices_per_module, (slot+1)*vertices_per_module)
        # Losing another observed section must not change the surviving source
        # variant, UVs, normals or original arclength slot around the ring.
        for field in (0, 1, 2, 4):
            assert np.array_equal(full[field][source], partial[field][retained])
