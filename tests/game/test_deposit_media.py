"""Saved native deposits keep their source frame and one presentation clock."""

from dataclasses import replace
from math import floor
from uuid import uuid4

import pygame
import pytest

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.events import EventPhase, EventQueue, SpatialEffectInteractionEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import WetSurface
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.world_authoring import set_world_tile_elevation
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import bind_choreography, bind_motion
from game.choreography_draw import load_choreography_media
from game.deposit_draw import deposit_draw_commands
from game.deposit_media import observed_deposits, register_deposit_starts
from game.environment_art import load_environment_art
from game.maintained_media import maintained_media_frame
from game.player_facts import ObjectDestroyedFact
from game.player_reduction import reduce_lineage
from game.playback_frame import sample_playback_frame
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera, HEIGHT_STEP_PIXELS
from game.replay import ObserverCapture, capture_history
from game.scene import load_scene_media, scene_actors
from tests.game.door_destruction_scenarios import attack_object, review_actor
from tests.game.liquid_barrel_scenarios import liquid_barrel_history
from tests.game.test_environment_presentation import _saved
from tests.game.test_liquid_barrel_replay import SPILL_CELLS, SURFACE_IDS, RESIDUE_IDS
from tests.game.test_liquid_surface_media import mixed_blood_history


WATER = "spatial_effect.material.water_surface"


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module")
def water_history():
    return liquid_barrel_history(liquid="water")


@pytest.fixture(scope="module")
def raster():
    pygame.init()
    screen = pygame.display.set_mode((600, 450))
    catalog = load_catalog()
    yield screen, catalog, SurfaceCache(catalog)
    pygame.quit()


def water_binding(data, source):
    authored = data.deposit_media[WATER]
    return authored.variants[source.deposit_uuid.int % len(authored.variants)]


def broken_head(native, data):
    before, roots = _saved(native)
    for root in roots:
        after = reduce_lineage(before, root)
        if any(isinstance(node.fact, ObjectDestroyedFact) for node in root.events):
            return before, after, root, bind_choreography(before, root, data)
        before = after
    pytest.fail("The native story did not disclose a barrel destruction")


@pytest.mark.parametrize("role", ("traveler", "witness"))
def test_saved_break_starts_at_authored_release_then_enters_sustain_without_reset(data, water_history, role):
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    before, after, root, group = broken_head(water_history.views[role], data)
    deposit, = observed_deposits(after, data)
    broken, = [node for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
    assert deposit.source.deposit_uuid == broken.lineage_uuid
    assert deposit.source.origin == (5, 4) and deposit.positions == SPILL_CELLS
    transition, = [row for row in group.world_transitions if row.destruction is not None]
    contact = transition.destruction
    assert contact is not None and contact.bank_id is not None
    bank = load_environment_art().banks[contact.bank_id]
    assert bank.release_frame == 6 and bank.frame_times_ms[6] == 500
    origin_ms = 2100
    starts = register_deposit_starts({}, before, data, absolute_start_ms=origin_ms,
        lineage=root, choreography=group)
    start = origin_ms + transition.start_ms + 500
    assert starts == {deposit.source.deposit_uuid: start}
    binding = water_binding(data, deposit.source)
    for layer in binding.layers:
        assert layer.applicationAssetId is not None
        phase = data.projectile_assets[layer.applicationAssetId].phases.impact
        assert phase is not None and phase.frames == 864 and phase.fps == 144
        assert binding.fps == 144 and binding.holdFrames == 288
        assert maintained_media_frame(data, binding, layer, start - .01, start) is None
        assert maintained_media_frame(data, binding, layer, start, start) == (layer.applicationAssetId, 0)
        assert maintained_media_frame(data, binding, layer, start + 5999, start) == (layer.applicationAssetId, 863)
        sustained = layer.assetId, binding.holdStartFrame
        assert maintained_media_frame(data, binding, layer, start + 6000, start) == sustained
        assert maintained_media_frame(data, binding, layer, start + 8000, start) == sustained
        # Absolute seek has no mutable advancing cursor.
        assert maintained_media_frame(data, binding, layer, start + 1000.001, start) == (layer.applicationAssetId, 144)
    assert origin_ms + group.complete_ms < start + 6000


@pytest.mark.parametrize("role", ("traveler", "witness"))
def test_real_following_actions_keep_the_same_discharge_date(data, water_history, role):
    state, roots = _saved(water_history.views[role])
    starts = {}
    absolute_ms = 0.
    first = None
    later_heads = 0
    for root in roots:
        after = reduce_lineage(state, root)
        motion = bind_motion(state, root, data)
        group = None if motion is not None else bind_choreography(state, root, data)
        starts = register_deposit_starts(starts, state, data, absolute_start_ms=absolute_ms,
            lineage=root, choreography=group, motion=motion)
        if first is not None:
            assert starts == first
            later_heads += 1
        elif starts:
            first = dict(starts)
        if motion is not None:
            absolute_ms += motion.complete_ms
        else:
            assert group is not None
            absolute_ms += group.complete_ms
        state = after
    assert first is not None and later_heads >= 3
    assert register_deposit_starts(starts, state, data, absolute_start_ms=absolute_ms) == first
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def changed_deposit_history(*, liquid="water", cold=False, remove=False, frozen=((6, 3), (6, 4), (6, 5)),
                            raised=False, include_cold_views=False):
    """A real break and retired wreck leave material, optionally transformed."""
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        if raised:
            author = uuid4()
            for x in range(3, 9):
                for y in range(2, 7):
                    set_world_tile_elevation((x, y), author_uuid=author, height=2,
                        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
        actors = {role: review_actor(game, role.title(), position, strength=18)
                  for role, position in (("traveler", (4, 4)), ("witness", (8, 6)))}
        traveler = actors["traveler"]
        barrel = build_authored_item(f"environment.blocker.{liquid}_barrel", traveler.uuid)
        barrel.place_on_grid((5, 4))
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        initialization = capture_interval(name="Before liquid discharge", start_cursor=0, end_cursor=cursor,
            observer_uuid=traveler.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initialization)
        attack_object(traveler, barrel, 8, additional_dice=(20,))
        barrel.retire()
        if frozen or remove:
            water, = get_map().get_spatial_conditions_at((5, 4))
            assert isinstance(water, WetSurface)
            if frozen:
                event = SpatialEffectInteractionEvent(source_entity_uuid=traveler.uuid,
                    operation=SpatialEffectInteractionOperation.FREEZE,
                    positions=frozen)
                event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
            if remove:
                assert water.deactivate()
        if cold:
            cursor = EventQueue.event_cursor()
        observers = tuple(ObserverCapture(role, actor.uuid, cursor) for role, actor in actors.items())
        if include_cold_views:
            observers += tuple(ObserverCapture(f"{role}-cold", actor.uuid, EventQueue.event_cursor())
                               for role, actor in actors.items())
        return capture_history(before, (), observers=observers)
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("frozen", (((6, 3), (6, 4), (6, 5)), ((5, 4),)))
def test_cold_partial_pool_survives_wreck_retirement_without_intro_or_recentering(data, frozen):
    history = changed_deposit_history(cold=True, frozen=frozen)
    for native in history.views.values():
        state, roots = _saved(native)
        assert not roots and not state.objects
        deposit, = observed_deposits(state, data)
        assert deposit.source.origin == (5, 4)
        assert deposit.positions == SPILL_CELLS - set(frozen)
        assert register_deposit_starts({}, state, data, absolute_start_ms=3000) == {}
        binding = water_binding(data, deposit.source)
        for layer in binding.layers:
            for now in (0, 500, 6000, 8000):
                assert maintained_media_frame(data, binding, layer, now, None) == (
                    layer.assetId, binding.holdStartFrame + floor(now * binding.fps / 1000) % binding.holdFrames)


def test_real_partial_transform_and_removal_drop_only_current_water_pieces(data):
    history = changed_deposit_history(remove=True)
    for native in history.views.values():
        state, roots = _saved(native)
        witnessed = []
        for root in roots:
            state = reduce_lineage(state, root)
            for deposit in observed_deposits(state, data):
                witnessed.append(deposit)
        assert any(deposit.positions == SPILL_CELLS for deposit in witnessed)
        assert any(deposit.positions == SPILL_CELLS - {(6, 3), (6, 4), (6, 5)} for deposit in witnessed)
        assert len({deposit.source for deposit in witnessed}) == 1
        assert observed_deposits(state, data) == ()
        assert state.senses is not None
        ice, = state.senses.spatial_effects.values()
        assert ice.name == "Ice Surface" and ice.deposit_source == witnessed[0].source
        assert register_deposit_starts({witnessed[0].source.deposit_uuid: 500}, state, data, absolute_start_ms=8000) == {}


def test_native_injury_contribution_survives_later_barrel_deposit_in_public_bytes():
    state, roots = _saved(mixed_blood_history().views["witness"])
    earlier = None
    for root in roots:
        state = reduce_lineage(state, root)
        blood = next((row for row in state.tiles[(5, 4)].residues if row.residue_id == "residue.blood"), None)
        if blood is not None and earlier is None:
            earlier = blood
    assert earlier is not None and blood is not None
    shaped = tuple(row for row in blood.contributions if row.ellipses)
    assert shaped == earlier.contributions
    spill, = [row for row in blood.contributions if row.deposit_source is not None]
    assert spill.ellipses == () and spill.amount == 4
    assert blood.condition_uuid == earlier.condition_uuid and blood.amount == 5


@pytest.mark.parametrize("quadrant", range(4))
def test_registered_water_draws_only_retained_native_pieces_and_seeks_stably(raster, data, water_history, quadrant):
    before, after, root, group = broken_head(water_history.views["traveler"], data)
    deposit, = observed_deposits(after, data)
    starts = register_deposit_starts({}, before, data, absolute_start_ms=0,
        lineage=root, choreography=group)
    start = starts[deposit.source.deposit_uuid]
    camera = Camera(quadrant=quadrant, viewport=(600, 450)).with_focus((5, 4))
    assert deposit_draw_commands(after, (deposit,), starts, data, start - .01, camera) == ()
    first = deposit_draw_commands(after, (deposit,), starts, data, start + 6500, camera)
    assert first and {row.evidence[1] for row in first} == SPILL_CELLS
    deposit_draw_commands(after, (deposit,), starts, data, start + 1000, camera)
    repeated = deposit_draw_commands(after, (deposit,), starts, data, start + 8500, camera)
    assert [(row.destination, row.evidence) for row in first] == [(row.destination, row.evidence) for row in repeated]
    assert [pygame.image.tobytes(row.surface, "RGBA") for row in first] == [
        pygame.image.tobytes(row.surface, "RGBA") for row in repeated]
    # Boundary-only restriction models a received subset, never changes origin.
    clipped = replace(deposit, positions=frozenset({(4, 4)}))
    draws = deposit_draw_commands(after, (clipped,), starts, data, start + 6500, camera)
    assert draws and {row.evidence[1] for row in draws} == {(4, 4)}
    assert clipped.source == deposit.source


@pytest.mark.parametrize("layout", ("door-closed", "door-open"))
def test_real_door_constrained_water_media_stays_in_received_cells_and_replaces_old_pool(raster, data, layout):
    screen, catalog, cache = raster
    history = liquid_barrel_history(liquid="water", layout=layout)
    for role, native in history.views.items():
        _, state, _, _ = broken_head(native, data)
        deposit, = observed_deposits(state, data)
        assert state.senses is not None
        observed, = (effect for effect in state.senses.spatial_effects.values()
                     if effect.content_ref.content_id == WATER)
        assert deposit.positions == frozenset(observed.positions)
        if role == "traveler":
            assert ((6, 4) in deposit.positions) is (layout == "door-open")
        if layout == "door-closed":
            assert all(x <= 5 for x, _ in deposit.positions)
        covered = frozenset({(deposit.source.deposit_uuid, WATER)})
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 4))
            commands = deposit_draw_commands(state, (deposit,), {}, data, 500, camera)
            assert commands and {row.evidence[1] for row in commands} <= set(observed.positions)
            evidence = draw_frame(screen, state, catalog, cache, camera, 0,
                show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
                extra_commands=commands, deposited_materials=covered)
            assert evidence is not None and evidence.matches
            assert any(len(row) > 6 and row[6] == "deposit_floor" for row in evidence.actual_draws)
            assert not any(row[2] == "particles.region.water" for row in evidence.actual_draws)
            pixels = pygame.image.tobytes(screen, "RGBA")
            draw_frame(screen, state, catalog, cache, camera, 0,
                show_grid=False, show_debug=False, mouse_position=None,
                extra_commands=tuple(row._replace(evidence=()) for row in commands), deposited_materials=covered)
            assert pygame.image.tobytes(screen, "RGBA") == pixels



def test_historical_frame_uses_release_date_without_holding_later_gameplay(raster, data, water_history):
    screen, _, _ = raster
    before, after, root, group = broken_head(water_history.views["traveler"], data)
    origin_ms = 1200
    starts = register_deposit_starts({}, before, data, absolute_start_ms=origin_ms,
        lineage=root, choreography=group)
    deposit, = observed_deposits(after, data)
    release_ms = starts[deposit.source.deposit_uuid] - origin_ms
    rows = {}
    body_media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})),
                                  data, body_rows=rows)
    media = load_choreography_media(group, body_rows=rows)
    font = pygame.font.Font(None, 16)
    camera = Camera(viewport=screen.get_size()).with_focus((5, 4))

    def sample(elapsed):
        return sample_playback_frame(before, after, data, elapsed, origin_ms + elapsed, camera,
            {}, body_media, font, font, choreography=group, choreography_media=media,
            deposit_starts=starts)

    before_release = sample(release_ms - 1)
    assert not any(row[4][6] in ("deposit_floor", "deposit_air") for row in before_release.commands)
    settled = sample(release_ms + 6500)
    assert settled.complete
    assert settled.deposited_materials == frozenset({(deposit.source.deposit_uuid, WATER)})
    assert any(row[4][6] == "deposit_floor" for row in settled.commands)
    assert group.complete_ms < release_ms + 6000
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_real_raised_water_keeps_floor_and_air_registration_after_wreck_retirement(raster, data):
    history = changed_deposit_history(raised=True, include_cold_views=True, frozen=())
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role in ("traveler", "witness"):
        before, at_break, root, group = broken_head(history.views[role], data)
        deposit, = observed_deposits(at_break, data)
        assert deposit.positions == SPILL_CELLS
        assert {at_break.tiles[position].elevation_steps for position in SPILL_CELLS} == {2}
        wreck, = at_break.objects.values()
        assert wreck.placement.position == deposit.source.origin == (5, 4)
        assert wreck.placement.base_height_steps == 2
        assert wreck.item.integrity is ItemIntegrity.DESTROYED
        assert wreck.item.remnant_state is not None
        starts = register_deposit_starts({}, before, data, absolute_start_ms=1200,
            lineage=root, choreography=group)
        start = starts[deposit.source.deposit_uuid]

        cold, roots = _saved(history.views[f"{role}-cold"])
        assert not roots and not cold.objects
        assert observed_deposits(cold, data) == (deposit,)
        assert {cold.tiles[position].elevation_steps for position in SPILL_CELLS} == {2}
        assert register_deposit_starts({}, cold, data, absolute_start_ms=9000) == {}
        # Only this projection boundary comparison lowers received support
        # heights; the actual history, material and source stay untouched.
        flat = replace(at_break, tiles={position: tile.model_copy(update={"elevation_steps": 0})
                                       for position, tile in at_break.tiles.items()})
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus((5, 4))
            # The approved airborne splash lasts about the first 470 ms;
            # subsequent intro frames contain settling floor material only.
            raised_draws = deposit_draw_commands(at_break, (deposit,), starts, data, start + 200, camera)
            flat_draws = deposit_draw_commands(flat, (deposit,), starts, data, start + 200, camera)
            assert {row.evidence[6] for row in raised_draws} == {"deposit_floor", "deposit_air"}
            assert len(raised_draws) == len(flat_draws)
            for actual, lowered in zip(raised_draws, flat_draws, strict=True):
                assert actual.evidence[7] == 2 and lowered.evidence[7] == 0
                assert actual.evidence[:7] == lowered.evidence[:7]
                assert actual.evidence[8:] == lowered.evidence[8:]
                assert actual.destination == (lowered.destination[0],
                    lowered.destination[1] - 2 * HEIGHT_STEP_PIXELS * camera.zoom)
                assert pygame.image.tobytes(actual.surface, "RGBA") == pygame.image.tobytes(lowered.surface, "RGBA")
            sustained = deposit_draw_commands(cold, (deposit,), {}, data, 500, camera)
            assert {row.evidence[1] for row in sustained if row.evidence[6] == "deposit_floor"} == SPILL_CELLS
            assert all(row.evidence[7] == 2 for row in sustained)


@pytest.mark.parametrize("liquid", ("water", "oil", "grease", "blood", "poison", "dread_blood"))
def test_all_authored_liquid_materials_replay_one_native_spill_in_both_views_and_four_cameras(raster, data, liquid):
    """Every material uses its real owner path, installed art and shared executor."""
    screen, catalog, cache = raster
    material_id = {**SURFACE_IDS, **RESIDUE_IDS}[liquid]
    authored = data.deposit_media[material_id]
    assert len(authored.variants) == 3
    history = changed_deposit_history(liquid=liquid, frozen=())
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    view_samples = []
    for native in history.views.values():
        before, at_break, root, group = broken_head(native, data)
        deposit, = observed_deposits(at_break, data)
        assert deposit.material_id == material_id and deposit.positions == SPILL_CELLS
        assert deposit.source.origin == (5, 4) and deposit.source.radius_cells == 1
        broken, = [node for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
        assert deposit.source.deposit_uuid == broken.lineage_uuid
        if liquid in SURFACE_IDS:
            assert at_break.senses is not None
            native_owner, = [effect for effect in at_break.senses.spatial_effects.values()
                            if effect.content_ref.content_id == material_id]
            assert native_owner.deposit_source == deposit.source
            assert frozenset(native_owner.positions) == deposit.positions
        else:
            for position in SPILL_CELLS:
                residue, = [row for row in at_break.tiles[position].residues if row.residue_id == material_id]
                contribution, = residue.contributions
                assert contribution.deposit_source == deposit.source
                assert contribution.amount == residue.amount == (5 if liquid == "blood" else 1)

        starts = register_deposit_starts({}, before, data, absolute_start_ms=1200,
            lineage=root, choreography=group)
        start = starts[deposit.source.deposit_uuid]
        transition, = [row for row in group.world_transitions if row.destruction is not None]
        assert transition.destruction is not None and transition.destruction.bank_id is not None
        bank = load_environment_art().banks[transition.destruction.bank_id]
        assert bank.release_frame is not None
        assert start == 1200 + transition.start_ms + bank.frame_times_ms[bank.release_frame]
        variant = authored.variants[deposit.source.deposit_uuid.int % 3]
        assert all(maintained_media_frame(data, variant, layer, start - .01, start) is None
                   for layer in variant.layers)
        selected = tuple(maintained_media_frame(data, variant, layer, start + 6500, start)
                         for layer in variant.layers)
        # Each subjective lineage has its own presentation duration. Compare
        # material phase at the same age after that view's witnessed rupture.
        view_samples.append((deposit.source, selected))

        # The captured retirement removes the item, while the deposit still
        # supplies its exact original frame and independently owned material.
        state, roots = _saved(native)
        for lineage in roots:
            state = reduce_lineage(state, lineage)
        assert not state.objects
        assert observed_deposits(state, data) == (deposit,)
        handled = frozenset({(deposit.source.deposit_uuid, material_id)})
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 4))
            commands = deposit_draw_commands(state, (deposit,), starts, data, start + 6500, camera)
            floor_commands = [row for row in commands if row.evidence[6] == "deposit_floor"]
            assert {row.evidence[1] for row in floor_commands} == SPILL_CELLS
            assert all((row.evidence[2], row.evidence[9]) in selected for row in commands)
            evidence = draw_frame(screen, state, catalog, cache, camera, 0,
                show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
                extra_commands=commands, deposited_materials=handled)
            assert evidence is not None and evidence.matches
            assert any(len(row) > 6 and row[6] == "deposit_floor" for row in evidence.actual_draws)
            assert not any(len(row) > 6 and row[6] == "ground_residue" for row in evidence.actual_draws)
    assert len(view_samples) == 2 and view_samples[0] == view_samples[1]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
