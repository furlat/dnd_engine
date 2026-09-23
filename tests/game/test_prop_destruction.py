"""Received prop integrity selects approved entry, break and settled pictures."""

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.content.items.world_prop_builders import WORLD_PROP_PROFILES
from game.app import draw_frame
from game.device_draw import device_treatment
from game.combat import actor_is_visible
from game.environment_animation import remnant_bank
from game.environment_art import load_environment_art, prop_state_key
from game.environment_draw import environment_command
from game.player_facts import ObjectDestroyedFact
from game.player_reduction import reduce_lineage
from game.projection import Camera, camera_pose
from tests.game.prop_destruction_scenarios import prop_destruction_history
from tests.game.test_environment_presentation import _render_head, _saved, raster as raster


CHESTS = ("environment.storage_chest", "environment.chest.fantasy_a1",
          "environment.chest.fantasy_a3", "environment.chest.fantasy_b1")
PROPS = ("environment.blocker.crate", "environment.blocker.oil_barrel",
         *WORLD_PROP_PROFILES)


@pytest.mark.parametrize("item_id", ("environment.furniture.wardrobe",
                                   "environment.furniture.bookshelf",
                                   "environment.furniture.storage_shelving",
                                   "environment.furniture.ingredient_shelves",
                                   "environment.furniture.pottery_cluster",
                                   "environment.furniture.large_crate_stack"))
def test_break_reveals_world_and_actor_contacts_at_authored_clearance(raster, item_id):
    captured = prop_destruction_history(item_id=item_id)
    for native in captured.views.values():
        state, roots = _saved(native)
        for root in roots:
            facts = [node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
            if not facts:
                state = reduce_lineage(state, root)
                continue
            fact, = facts
            after, group, render = _render_head(raster, state, root)
            transition, = (row for row in group.world_transitions if row.field == "destruction")
            assert transition.destruction is not None and transition.destruction.bank_id is not None
            bank = load_environment_art().banks[transition.destruction.bank_id]
            assert 0 < bank.state_change_frame < bank.frame_count
            clearance_ms = transition.start_ms + bank.frame_times_ms[bank.state_change_frame]
            revealed = {identity for identity, actor in after.actors.items()
                        if actor_is_visible(after, actor)
                        and (identity not in state.actors or not actor_is_visible(state, state.actors[identity]))}
            assert revealed
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus(fact.placement.position)
                for at in (transition.start_ms, clearance_ms - .001):
                    frame, drawings, pixels = render(camera, at)
                    assert frame.displayed.senses is not None and state.senses is not None
                    assert frame.displayed.senses.visible == state.senses.visible
                    assert frame.displayed.objects[fact.object_uuid].placement == state.objects[fact.object_uuid].placement
                    assert not {str(identity) for identity in revealed}.intersection(
                        actor.contact.actor_uuid for actor in frame.actors)
                    body, = (row for row in drawings if len(row) > 9 and row[0] == fact.object_uuid)
                    assert body[6] == "environment_wreck"
                    assert body[9] == (0 if at == transition.start_ms else bank.state_change_frame - 1)
                    reached, _, _ = render(camera, clearance_ms)
                    assert reached.displayed.senses == after.senses
                    assert reached.displayed.objects[fact.object_uuid] == after.objects[fact.object_uuid]
                    assert {str(identity) for identity in revealed} <= {
                        actor.contact.actor_uuid for actor in reached.actors}
                    np.testing.assert_array_equal(pixels, render(camera, at)[2])
            state = after
    assert EventQueue.event_cursor() == 0


def test_banked_world_art_accepts_very_bright_light_without_changing_alpha(raster):
    image = pygame.Surface((1, 1), pygame.SRCALPHA)
    image.fill((100, 50, 250, 121))
    result = device_treatment(image, (1.08, 1.08, 1.04))
    assert tuple(result.get_at((0, 0))) == (108, 54, 255, 121)
    assert tuple(image.get_at((0, 0))) == (100, 50, 250, 121)


@pytest.mark.parametrize("item_id,opened", [(item, opened) for item in CHESTS for opened in (False, True)]
                         + [(item, False) for item in PROPS])
def test_native_prop_break_keeps_one_body_and_exact_authored_bank_through_seek(raster, item_id, opened):
    art = load_environment_art()
    captured = prop_destruction_history(item_id=item_id, opened=opened)
    for native in captured.views.values():
        state, roots = _saved(native)
        witnessed = 0
        for root in roots:
            facts = [node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)]
            if not facts:
                state = reduce_lineage(state, root)
                continue
            fact, = facts
            witnessed += 1
            before = state.objects[fact.object_uuid]
            assert before.item.integrity is ItemIntegrity.INTACT
            assert before.item.item_id == item_id
            after, group, render = _render_head(raster, state, root)
            assert not group.gaps
            same = after.objects[fact.object_uuid]
            assert same.item.item_id == item_id and same.item.integrity is ItemIntegrity.DESTROYED
            # Physical blocking/bands can change; the body's mount and covered
            # supports remain the same received geometry throughout its break.
            assert same.placement.position == before.placement.position
            assert same.placement.covered_supports == before.placement.covered_supports
            assert same.placement.base_height_steps == before.placement.base_height_steps
            assert same.placement.orientation == before.placement.orientation
            if item_id in CHESTS:
                assert not any(obj.item.item_id == "consumable.healing_potion" for obj in state.objects.values())
                loot, = (obj for obj in after.objects.values() if obj.item.item_id == "consumable.healing_potion")
                assert loot.placement.position == same.placement.position
            transition, = (row for row in group.world_transitions if row.field == "destruction")
            assert transition.destruction is not None
            bank = remnant_bank(art, item_id, same.item.remnant_state, outcome=same.item.destruction_outcome)
            assert bank is not None and transition.destruction.bank_id == bank.identity
            intact_key = prop_state_key(art.props[item_id], before.item.is_open)
            assert intact_key is not None
            intact = art.props[item_id].intact[intact_key]
            assert state.senses is not None
            attacker_uuid = captured.before.observer_uuid
            contact = state.senses.entities.get(attacker_uuid)
            attacker_visible = state.observer_uuid == attacker_uuid or contact is not None and contact.visual
            if attacker_visible:
                gesture, = group.body_actions
                assert transition.start_ms == gesture.effect_ms
            else:
                # The opposite witness can see the cupboard breaking without
                # seeing the attacker behind it. Do not invent that body's pose.
                assert state.observer_uuid != attacker_uuid
                assert not group.body_actions
                assert transition.start_ms == 0
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus(before.placement.position)
                pose = camera_pose("east", quadrant)
                def command(selected, frame):
                    return environment_command(selected, frame, identity=fact.object_uuid,
                        position=before.placement.position, elevation=before.placement.base_height_steps,
                        pose=pose, boundary_pose=None, camera=camera, multiplier=(1, 1, 1))
                entry, fracture = command(intact, 0), command(bank, 0)
                assert entry.destination == fracture.destination
                assert pygame.image.tobytes(entry.surface, "RGBA") == pygame.image.tobytes(fracture.surface, "RGBA")
                wind = None
                if transition.start_ms > 0:
                    _, drawings, wind = render(camera, transition.start_ms - .001, actors=False)
                    body, = (row for row in drawings if len(row) > 9 and row[0] == fact.object_uuid)
                    assert body[2] == intact.identity and body[6] == "environment_prop" and body[8] == pose
                struck, drawings, contact_pixels = render(camera, transition.start_ms, actors=False)
                assert struck.displayed.objects[fact.object_uuid].item.integrity is (
                    ItemIntegrity.INTACT if bank.state_change_frame else ItemIntegrity.DESTROYED)
                body, = (row for row in drawings if len(row) > 9 and row[0] == fact.object_uuid)
                assert body[6] == "environment_wreck" and body[8] == pose and body[9] == 0
                _, drawings, settled = render(camera, group.complete_ms, actors=False)
                body, = (row for row in drawings if len(row) > 9 and row[0] == fact.object_uuid)
                assert body[9] == bank.frame_count - 1
                np.testing.assert_array_equal(settled, render(camera, 0, idle=True, actors=False)[2])
                np.testing.assert_array_equal(contact_pixels, render(camera, transition.start_ms, actors=False)[2])
                if wind is not None:
                    np.testing.assert_array_equal(wind, render(camera, transition.start_ms - .001, actors=False)[2])
            state = after
        assert witnessed == 1
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("item_id,opened", (("environment.chest.fantasy_b1", True),
                                          ("environment.furniture.bed", False),
                                          ("environment.furniture.wardrobe", False),
                                          ("environment.furniture.winged_statue", False)))
def test_late_observer_initialization_draws_settled_prop_without_replaying_fracture(raster, item_id, opened):
    captured = prop_destruction_history(item_id=item_id, opened=opened, late_snapshot=True)
    screen, catalog, cache, _, _ = raster
    for native in captured.views.values():
        state, roots = _saved(native)
        assert not roots
        body, = (obj for obj in state.objects.values() if obj.item.item_id == item_id)
        assert body.item.integrity is ItemIntegrity.DESTROYED
        bank = remnant_bank(load_environment_art(), item_id, body.item.remnant_state,
                            outcome=body.item.destruction_outcome)
        assert bank is not None
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(body.placement.position)
            evidence = draw_frame(screen, state, catalog, cache, camera, 0,
                show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True)
            assert evidence is not None
            drawn, = (row for row in evidence.actual_draws if len(row) > 9 and row[0] == body.item.item_uuid)
            assert drawn[6] == "environment_wreck" and drawn[9] == bank.frame_count - 1
