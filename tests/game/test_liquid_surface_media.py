"""Real barrel state produces bounded floor media through passive public replay."""

from collections.abc import Iterator
from dataclasses import replace

import numpy as np
import pygame
import pytest

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.events import EventPhase, EventQueue, SpatialEffectInteractionEvent
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import OilSurface, WetSurface
from dnd.types.spatial_effects import SpatialEffectInteractionIntensity, SpatialEffectInteractionOperation
from game.app import FrameEvidence, draw_frame
from game.assets import AssetCatalog, SurfaceCache, load_catalog
from game.player_facts import ObjectDestroyedFact, PlayerState
from game.player_reduction import reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH
from game.replay import CapturedHistory, ObserverCapture, capture_history
from game.surface_residue import ResidueSurfaceCache, liquid_surface_image
from tests.game.door_destruction_scenarios import review_actor, walk
from tests.game.liquid_barrel_scenarios import Liquid, liquid_barrel_history
from tests.game.test_environment_presentation import _saved


@pytest.fixture(scope="module")
def raster() -> Iterator[tuple[pygame.Surface, AssetCatalog, SurfaceCache]]:
    pygame.init()
    screen = pygame.display.set_mode((600, 450))
    catalog = load_catalog()
    yield screen, catalog, SurfaceCache(catalog)
    pygame.quit()


def render(raster: tuple[pygame.Surface, AssetCatalog, SurfaceCache], state: PlayerState,
           quadrant: int) -> tuple[FrameEvidence, np.ndarray]:
    screen, catalog, cache = raster
    camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 4))
    evidence = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
        show_debug=False, mouse_position=None, collect_evidence=True)
    assert evidence is not None and evidence.matches
    return evidence, pygame.surfarray.array3d(screen)


@pytest.mark.parametrize("liquid,asset", (
    ("oil", "particles.region.oil"), ("water", "particles.region.water"),
    ("poison", "particles.region.poison"), ("blood", "particles.region.blood"),
    ("dread_blood", "particles.region.dread"),
))
def test_actual_barrel_spill_has_one_observed_pool_and_remains_after_passive_replay(
    raster: tuple[pygame.Surface, AssetCatalog, SurfaceCache], liquid: Liquid, asset: str,
) -> None:
    history = liquid_barrel_history(liquid=liquid)
    for native in history.views.values():
        state, roots = _saved(native)
        initial, _ = render(raster, state, 0)
        assert not any(row[2] == asset for row in initial.actual_draws)
        for root in roots:
            after = reduce_lineage(state, root)
            if any(isinstance(node.fact, ObjectDestroyedFact) for node in root.events):
                for quadrant in range(4):
                    evidence, first = render(raster, after, quadrant)
                    positions = {row[1] for row in evidence.actual_draws if row[2] == asset}
                    assert positions == {(x, y) for x in range(4, 7) for y in range(3, 6)}
                    # Native ground state is available immediately at the
                    # contact; its settled image needs no live entity/query.
                    np.testing.assert_array_equal(first, render(raster, after, quadrant)[1])
            state = after
        for quadrant in range(4):
            evidence, _ = render(raster, state, quadrant)
            positions = {row[1] for row in evidence.actual_draws if row[2] == asset}
            assert positions == {(x, y) for x in range(4, 7) for y in range(3, 6)}
        assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("identity", (
    "residue.blood", "residue.poison", "residue.dread_blood",
    "spatial_effect.material.water_surface", "spatial_effect.material.oil",
))
def test_pool_pixels_stay_inside_the_recorded_cell_and_amount_changes_density(
    raster: tuple[pygame.Surface, AssetCatalog, SurfaceCache], identity: str,
) -> None:
    style = raster[1].liquid_surfaces[identity]
    cache = ResidueSurfaceCache()
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1)
        small = liquid_surface_image(cache, style, (5, 4), camera, (1, 1, 1), amount=1, max_amount=5)
        pool = liquid_surface_image(cache, style, (5, 4), camera, (1, 1, 1), amount=5, max_amount=5)
        alpha = pygame.surfarray.array_alpha(pool)
        x, y = np.indices(pool.size)
        inside = (abs((x + .5 - pool.width / 2) / (TILE_WIDTH / 2))
                  + abs((y + .5 - pool.height / 2) / (TILE_HEIGHT / 2))) <= 1
        assert not alpha[~inside].any()
        assert 0 < pygame.surfarray.array_alpha(small).sum() < alpha.sum()
        assert pygame.image.tobytes(pool, "RGBA") == pygame.image.tobytes(
            liquid_surface_image(cache, style, (5, 4), camera, (1, 1, 1), amount=5, max_amount=5), "RGBA")


def material_replacement_history(liquid: str) -> CapturedHistory:
    """Exercise native removal and oil's existing ignition interaction."""
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        witness = review_actor(game, "Witness", (4, 4))
        barrel = build_authored_item(f"environment.blocker.{liquid}_barrel", witness.uuid)
        barrel.place_on_grid((5, 4))
        witness.update_entity_senses()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Before spill", start_cursor=0, end_cursor=cursor,
            observer_uuid=witness.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        barrel.receive_damage(12, DamageType.BLUDGEONING, witness.uuid)
        material, = get_map().get_spatial_conditions_at((5, 4))
        if liquid == "oil":
            assert isinstance(material, OilSurface)
            event = SpatialEffectInteractionEvent(source_entity_uuid=witness.uuid,
                positions=tuple(sorted(material.affected_positions)),
                operation=SpatialEffectInteractionOperation.IGNITE,
                intensity=SpatialEffectInteractionIntensity.STRONG)
            result = event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
            assert not result.canceled
        else:
            assert isinstance(material, WetSurface)
            assert material.deactivate()
        return capture_history(before, (), observers=(ObserverCapture("witness", witness.uuid, cursor),))
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("liquid", ("water", "oil"))
def test_native_removal_or_replacement_removes_old_pool_in_all_cameras(
    raster: tuple[pygame.Surface, AssetCatalog, SurfaceCache], liquid: str,
) -> None:
    history = material_replacement_history(liquid)
    state, roots = _saved(history.views["witness"])
    asset = f"particles.region.{liquid}"
    seen = False
    for root in roots:
        state = reduce_lineage(state, root)
        if any(row[2] == asset for row in render(raster, state, 0)[0].actual_draws):
            seen = True
    assert seen
    assert state.senses is not None
    if liquid == "oil":
        assert any(effect.name == "Fire Surface" for effect in state.senses.spatial_effects.values())
    assert all(effect.name != ("Oil Surface" if liquid == "oil" else "Wet Surface")
               for effect in state.senses.spatial_effects.values())
    for quadrant in range(4):
        evidence, final = render(raster, state, quadrant)
        assert not any(row[2] == asset for row in evidence.actual_draws)
        # Unknown fire media stays an explicit gap; it cannot keep drawing oil.
        screen, catalog, _ = raster
        no_liquids = replace(catalog, liquid_surfaces={})
        np.testing.assert_array_equal(final, render((screen, no_liquids, SurfaceCache(no_liquids)), state, quadrant)[1])
    assert EventQueue.event_cursor() == 0


def mixed_blood_history() -> CapturedHistory:
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        witness = review_actor(game, "Witness", (4, 4))
        injured = review_actor(game, "Injured", (5, 4))
        witness.update_entity_senses()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Before injury and spill", start_cursor=0, end_cursor=cursor,
            observer_uuid=witness.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        injured.receive_damage(1, DamageType.SLASHING, witness.uuid)
        walk(injured, (6, 4))
        barrel = build_authored_item("environment.blocker.blood_barrel", witness.uuid)
        barrel.place_on_grid((5, 4))
        barrel.receive_damage(12, DamageType.BLUDGEONING, witness.uuid)
        return capture_history(before, (), observers=(ObserverCapture("witness", witness.uuid, cursor),))
    finally:
        game.close()
        reset_engine_runtime()


def test_barrel_pool_adds_unshaped_quantity_without_losing_old_native_injury_geometry(
    raster: tuple[pygame.Surface, AssetCatalog, SurfaceCache],
) -> None:
    state, roots = _saved(mixed_blood_history().views["witness"])
    deposits = []
    for root in roots:
        state = reduce_lineage(state, root)
        blood = next((row for row in state.tiles[(5, 4)].residues if row.residue_id == "residue.blood"), None)
        if blood is not None:
            deposits.append(blood)
    assert deposits[0].amount == 1 and deposits[0].contributions
    assert deposits[-1].amount == 5
    assert deposits[0].condition_uuid == deposits[-1].condition_uuid
    original = deposits[0].contributions
    assert deposits[-1].contributions[:len(original)] == original
    spill, = deposits[-1].contributions[len(original):]
    assert spill.ellipses == () and spill.deposit_source is not None
    assert spill.amount == deposits[-1].amount - deposits[0].amount == 4
    screen, catalog, cache = raster
    no_pool = replace(catalog, liquid_surfaces={})
    for quadrant in range(4):
        _, with_pool = render((screen, catalog, cache), state, quadrant)
        _, old_shapes = render((screen, no_pool, SurfaceCache(no_pool)), state, quadrant)
        assert np.any(with_pool != old_shapes)
    assert EventQueue.event_cursor() == 0
