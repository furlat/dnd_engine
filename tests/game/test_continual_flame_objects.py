"""Legal environment/device/static items carry one recorded flame through map changes."""

from dataclasses import replace
from types import MappingProxyType
from uuid import uuid4

import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall, build_standing_torch
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import ContinualFlame
from dnd.types.world import CardinalDirection
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import load_catalog, SurfaceCache
from game.choreography import bind_choreography
from game.item_attachment_lifetime import register_item_attachment_starts
from game.player_reduction import reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera
from game.replay import capture_history, ObserverCapture
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def media():
    pygame.init()
    pygame.display.set_mode((1, 1))
    data, catalog = load_animation_data(), load_catalog()
    yield data, catalog, SurfaceCache(catalog)
    pygame.quit()


def recorded_object(item_id):
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        caster = Entity.create(uuid4(), "Caster", config=EntityConfig(position=(3, 6),
            action_economy=ActionEconomyConfig(spell_slots={2: 1}),
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence")))
        register_spell(caster, ContinualFlame)
        caster.compose_entity()
        game.deploy_entity(caster, caster.position)
        wall = item_id in ("wall", "corner")
        item = (build_directional_wall() if wall else
                build_standing_torch() if item_id == "environment.standing_torch"
                else build_authored_item(item_id, caster.uuid))
        if wall:
            # Explicitly targetable authored structure; legacy topology-only
            # walls intentionally do not expose object actions by default.
            item.is_targetable = True
            item.include_in_senses_objects = True
            item.include_in_available_object_actions = True
        item.place_on_grid((4, 6), boundary_direction=CardinalDirection.NORTH if wall else None)
        if item_id == "corner":
            build_directional_wall().place_on_grid((4, 6), boundary_direction=CardinalDirection.EAST)
            build_directional_wall().place_on_grid((4, 8), boundary_direction=CardinalDirection.EAST)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Object flame initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        action, selected = next((action, target) for action in get_available_actions(caster).all_actions
            if action.behavior_id == "spell.continual_flame" for target in action.valid_targets
            if target.target_uuid == item.uuid)
        result = execute_available_action(caster, action, selected)
        assert result is not None and not result.canceled
        condition = item.active_conditions["Continual Flame"]
        effect_uuid = condition.uuid
        # These nonportable fixtures relocate through the existing exact world
        # placement operation; this does not invent a player pickup capability.
        assert get_map().remove_object(item.uuid)
        item.place_on_grid((4, 8), boundary_direction=CardinalDirection.NORTH if wall else None)
        assert item.active_conditions["Continual Flame"] is condition
        item.destroy()
        assert not condition.applied
        captured = capture_history(before, (), observers=(ObserverCapture("caster", caster.uuid, baseline),))
        return captured, item.uuid, effect_uuid
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("item_id", ("environment.furniture.clay_stove",
    "environment.fireball_cannon", "environment.standing_torch", "wall", "corner"))
def test_saved_real_object_flame_reaches_map_painter_and_keeps_one_birth(media, item_id):
    data, catalog, cache = media
    history, identity, owner = recorded_object(item_id)
    state, roots = player_history(history, role="caster")
    starts, clock, retained, positions = {}, 0., [], set()
    for root in roots:
        group = bind_choreography(state, root, data)
        starts = register_item_attachment_starts(starts, state, data,
            absolute_start_ms=clock, lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        clock += group.complete_ms + 50
        obj = state.objects.get(identity)
        if obj is not None and obj.item.item_effects:
            positions.add(obj.placement.position)
            retained.append((state, starts, clock))
    assert positions == {(4, 6), (4, 8)}
    assert len(starts) == 1 and starts[owner].item_uuid == identity
    assert starts[owner].applied_ms is not None
    assert all(row[1][owner] == starts[owner] for row in retained)
    assert identity not in state.objects or not state.objects[identity].item.item_effects
    assert EventQueue.event_cursor() == 0
    plain_data = replace(data, item_attachments=MappingProxyType({}))

    def render(state, selected_data, camera, starts, clock):
        screen = pygame.Surface(camera.viewport, pygame.SRCALPHA)
        evidence = draw_frame(screen, state, catalog, cache, camera, clock / 1000,
            show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
            animation_data=selected_data, item_starts=starts).evidence
        assert evidence is not None and evidence.matches
        return pygame.image.tobytes(screen, "RGBA"), evidence.actual_draws

    # Each native position reaches the same ordinary map renderer in all cameras.
    for position in sorted(positions):
        shown, dates, clock = next(row for row in retained
            if row[0].objects[identity].placement.position == position)
        obj = shown.objects[identity]
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(position)
            plain, plain_draws = render(shown, plain_data, camera, dates, clock + 2000)
            flame, flame_draws = render(shown, data, camera, dates, clock + 2000)
            assert flame != plain
            assert all(row in flame_draws for row in plain_draws)
            assert any(row[:2] == (identity, "item_attachment") for row in flame_draws)
            suppressed = replace(shown, objects={**shown.objects, identity: replace(obj,
                item=replace(obj.item, suppression_provider_uuids=(owner,)))})
            assert render(suppressed, data, camera, dates, clock + 2000)[0] == plain
        assert shown.senses is not None
        hidden = replace(shown, senses=replace(shown.senses,
            objects={key: value for key, value in shown.senses.objects.items() if key != identity}))
        camera = Camera(viewport=(640, 480)).with_focus(position)
        assert render(hidden, data, camera, dates, clock + 2000)[0] == render(
            hidden, plain_data, camera, dates, clock + 2000)[0]
    camera = Camera(viewport=(640, 480)).with_focus((4, 8))
    assert render(state, data, camera, starts, clock + 2000)[0] == render(
        state, plain_data, camera, starts, clock + 2000)[0]
