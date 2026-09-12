"""Native turn/equipment facts through the shared game and gallery compositor."""

import json
from typing import Literal

import pygame
import pytest

from dnd.actions import AttackEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.equipment import ArmorEquipEvent, ArmorUnequipEvent, EquipmentEvent, WeaponUnequipEvent
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.item_types import ItemLocation
from game.animation import body_clip, sample_equipment
from game.animation_draw import LoadedBodyRows
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands
from game.animation_types import AnimationData
from game.attack import BoundAttack, sample_attack
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from game.presentation import reduce_lineage
from game.replay import CapturedHistory
from game.player_reduction import reduce_lineage as reduce_player_lineage
from tests.game.player_helpers import player_history
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.equipment_scenarios import equipment_sequence_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


@pytest.fixture(scope="module", params=("weapon", "wardrobe"))
def history(request: pytest.FixtureRequest) -> CapturedHistory:
    replacement: Literal["weapon", "wardrobe"] = request.param
    captured = equipment_sequence_history(replacement=replacement)
    return captured


@pytest.fixture(scope="module")
def pygame_runtime():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        try:
            pygame.display.set_mode((960, 640))
            yield
        finally:
            pygame.quit()


def test_same_turn_replacement_keeps_real_roots_and_native_item_ac(
    history: CapturedHistory,
) -> None:
    before, roots = history.before, history.lineages
    attacks = tuple(root.root for root in roots if isinstance(root.root, AttackEvent))
    assert len(attacks) == 2 and attacks[0].turn_execution_id == attacks[1].turn_execution_id
    assert attacks[0].turn_execution_id is not None
    assert attacks[0].behavior_id == "action.attack"
    assert attacks[1].behavior_id == "action.feature.extra_attack"
    assert attacks[0].weapon_slot.value == "MELEE_MAIN" and attacks[1].weapon_slot.value == "RANGED_MAIN"
    notifications = tuple(root.root for root in roots if isinstance(root.root, EquipmentEvent))
    assert len(notifications) == 2
    if any(isinstance(event, ArmorEquipEvent) for event in notifications):
        assert any(isinstance(event, ArmorUnequipEvent) for event in notifications)
    incoming = tuple(root.root for root in roots if isinstance(root.root, ItemLocationStateEvent)
                     and root.root.location is ItemLocation.EQUIPMENT)
    assert len(incoming) == 1
    event = incoming[0]
    identity = event.item_state.item_uuid
    assert event.equipment_slot is not None
    current = before
    for root in roots:
        assert root.dispositions == () and root.root.parent_lineage is None
        prior = current
        current = reduce_lineage(current, root)
        if isinstance(root.root, EquipmentEvent):
            assert current.actors == prior.actors
        if root.root.uuid == event.uuid:
            assert dict(current.actors[before.observer_uuid].equipment)[event.equipment_slot.value] == identity
            assert current.actors[before.observer_uuid].armor_class == event.entity_armor_class_after
    assert current.actors[before.observer_uuid].active_weapon_set is WeaponSet.RANGED
    assert before.actors[before.observer_uuid].active_weapon_set is WeaponSet.MELEE
    assert current.current_actor_uuid == before.current_actor_uuid


def test_shared_equipment_gesture_preserves_identity_until_settlement_and_attack_switches_on_entry(
    history: CapturedHistory,
    data: AnimationData, pygame_runtime: None,
) -> None:
    before, roots = player_history(history)
    initial = before
    latest = before
    for root in roots:
        latest = reduce_player_lineage(latest, root)
    appearances = list(scene_actors(before, data, {}))
    for root in roots:
        after = reduce_player_lineage(before, root)
        appearances.extend(scene_actors(after, data, {}))
        before = after
    body_rows: LoadedBodyRows = {}
    media = load_scene_media(tuple(appearances), data, body_rows=body_rows)
    before = initial
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx), bold=True)
                  for style in (data.number_style, data.badge_style))
    equipment_count = 0
    for root, native in zip(roots, history.lineages, strict=True):
        contacts = {actor.contact.actor_uuid: actor.contact for actor in scene_actors(before, data, {})}
        group = bind_choreography(before, root, data, contacts=contacts)
        assert group.gaps == ()
        after = reduce_player_lineage(before, root)
        if isinstance(native.root, AttackEvent):
            node, = group.nodes
            assert isinstance(node.bound, BoundAttack)
            assert not group.equipment
            assert node.start_ms == 0 and group.complete_ms == node.bound.timeline.complete_ms
            if native.root.weapon_slot.value == "RANGED_MAIN":
                assert before.actors[before.observer_uuid].visual_loadout.active_weapon_set is WeaponSet.MELEE
                layers = node.bound.appearances[str(before.observer_uuid)]
                # The actual Fighter premade carries the authored longbow.
                assert next(layer.category for layer in layers if layer.slot == "weapon") == "Ranged4"
                group_media = load_choreography_media(group, body_rows=body_rows)
                identity = node.bound.timeline.source.actor_uuid
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(node.bound.timeline.source.grid)
                    visible_bow = False
                    for elapsed in (0, node.bound.timeline.contact_ms / 2):
                        frame = sample_playback_frame(before, after, data, elapsed, 5000 + elapsed,
                            camera, {}, media, *fonts, choreography=group, choreography_media=group_media)
                        drawn = next(command for command in frame.commands
                                     if command[4][0] == identity and command[4][6] == "actor")
                        body = next(body for body in sample_attack(node.bound.timeline, elapsed).bodies
                                    if body.actor_uuid == identity)
                        without_bow = next(command for command in actor_draw_commands(
                            data, body, node.bound.timeline.source,
                            tuple(layer for layer in layers if layer.slot != "weapon"),
                            group_media.attacks[node.event_uuid], camera) if command[4][6] == "actor")
                        visible_bow |= pygame.image.tobytes(drawn[1], "RGBA") != pygame.image.tobytes(without_bow[1], "RGBA")
                    assert visible_bow, f"Actual longbow must contribute visible pixels in view {quadrant}"
        if group.equipment:
            equipment_count += 1
            cue, = group.equipment
            timeline = cue.bound.timeline
            identity = timeline.actor.actor_uuid
            old = cue.bound.appearances[identity]
            new = cue.bound.replacement
            assert old != new
            recipe = json.loads(data.context_source_json)["contexts"]["equipment_transition"]
            assert timeline.recipe.model_dump(mode="json") == recipe
            clip = body_clip(data, timeline.actor, timeline.recipe.bodyClip)
            commit = recipe["commitFrame"] * 1000 / (clip.fps * recipe["bodyPlaybackSpeed"])
            assert sample_equipment(timeline, commit).body.frame == recipe["commitFrame"]
            held = sample_choreography(group, commit)
            assert held.displayed.actors[before.observer_uuid].visual_loadout.layers == before.actors[before.observer_uuid].visual_loadout.layers
            assert latest.actors[before.observer_uuid].visual_loadout.layers != before.actors[before.observer_uuid].visual_loadout.layers
            assert sample_choreography(group, commit) == held
            group_media = load_choreography_media(group, body_rows=body_rows)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(timeline.actor.grid)
                for elapsed in (0, commit, group.complete_ms - .001, group.complete_ms):
                    frame = sample_playback_frame(before, after, data, elapsed, 5000 + elapsed,
                        camera, {}, media, *fonts, choreography=group, choreography_media=group_media)
                    actor = next(actor for actor in frame.actors if actor.contact.actor_uuid == identity)
                    expected_layers = new if elapsed >= group.complete_ms else old
                    assert actor.layers == expected_layers
                    commands = tuple(command for command in frame.commands
                                     if command[4][0] == identity and command[4][6] == "actor")
                    assert len(commands) == 1
                    if elapsed < group.complete_ms:
                        body = sample_equipment(timeline, elapsed).body
                        wrong = next(command for command in actor_draw_commands(
                            data, body, actor.contact, new, media, camera) if command[4][6] == "actor")
                        assert pygame.image.tobytes(commands[0][1], "RGBA") != pygame.image.tobytes(wrong[1], "RGBA")
                    else:
                        idle = sample_playback_frame(after, None, data, 0, 5000 + elapsed,
                            camera, frame.facings, media, *fonts, positions=frame.positions)
                        idle_body = next(command for command in idle.commands
                                         if command[4][0] == identity and command[4][6] == "actor")
                        assert commands[0][2:] == idle_body[2:]
                        assert pygame.image.tobytes(commands[0][1], "RGBA") == pygame.image.tobytes(idle_body[1], "RGBA")
        before = after
    assert equipment_count == 1 and before == latest


def test_removed_active_sword_commits_surviving_bow_at_authored_frame_before_ranged_attack(
    data: AnimationData, pygame_runtime: None,
) -> None:
    captured = equipment_sequence_history(replacement="remove-weapon")
    before, roots = player_history(captured)
    identity = before.observer_uuid
    initial = before.actors[identity]
    equipment = {item.slot: item.item_uuid for item in initial.visual_loadout.layers}
    sword, bow = equipment[WeaponSlot.MELEE_MAIN.value], equipment[WeaponSlot.RANGED_MAIN.value]
    assert WeaponSlot.MELEE_OFF.value not in equipment
    assert initial.visual_loadout.active_weapon_set is WeaponSet.MELEE
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx), bold=True)
                  for style in (data.number_style, data.badge_style))
    saw_switch = False
    sword_stored = False
    for root, native in zip(roots, captured.lineages, strict=True):
        after = reduce_player_lineage(before, root)
        group = bind_choreography(before, root, data)
        assert not group.gaps
        if isinstance(native.root, ItemLocationStateEvent) and native.root.item_state.item_uuid == sword:
            assert native.root.location is ItemLocation.INVENTORY
            sword_stored = True
        if isinstance(native.root, WeaponUnequipEvent):
            saw_switch = True
            assert native.root.item_uuid == sword and native.root.active_weapon_set_after is WeaponSet.RANGED
            assert before.actors[identity].visual_loadout.active_weapon_set is WeaponSet.MELEE
            assert after.actors[identity].visual_loadout.active_weapon_set is WeaponSet.RANGED
            cue, = group.equipment
            timeline = cue.bound.timeline
            assert timeline.recipe.bodyClip == "Taunt" and timeline.recipe.commitFrame == 4
            old_weapon, = (layer for layer in cue.bound.appearances[str(identity)] if layer.slot == "weapon")
            body_rows: LoadedBodyRows = {}
            media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(after, data, {})), data, body_rows=body_rows)
            group_media = load_choreography_media(group, body_rows=body_rows)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(timeline.actor.grid)
                for elapsed, expected in ((timeline.commit_ms - .001, WeaponSet.MELEE),
                                          (timeline.commit_ms, WeaponSet.RANGED),
                                          (timeline.complete_ms, WeaponSet.RANGED)):
                    frame = sample_playback_frame(before, after, data, elapsed, elapsed, camera, {}, media,
                                                  *fonts, choreography=group, choreography_media=group_media)
                    assert frame.displayed.actors[identity].visual_loadout.active_weapon_set is expected
                    actor, = (actor for actor in frame.actors if actor.contact.actor_uuid == str(identity))
                    weapon, = (layer for layer in actor.layers if layer.slot == "weapon")
                    assert weapon.category == ("Ranged4" if expected is WeaponSet.RANGED else old_weapon.category)
                    # Compare the actual composed body with and without its
                    # selected weapon, at the same sampled pose and camera.
                    body = sample_equipment(timeline, elapsed).body
                    drawn, = (command for command in frame.commands
                              if command[4][0] == str(identity) and command[4][6] == "actor")
                    bare, = (command for command in actor_draw_commands(data, body, actor.contact,
                        tuple(layer for layer in actor.layers if layer.slot != "weapon"), media, camera)
                             if command[4][6] == "actor")
                    assert pygame.image.tobytes(drawn[1], "RGBA") != pygame.image.tobytes(bare[1], "RGBA")
        if isinstance(native.root, AttackEvent) and native.root.weapon_slot is WeaponSlot.RANGED_MAIN:
            assert saw_switch and sword_stored
            assert before.actors[identity].visual_loadout.active_weapon_set is WeaponSet.RANGED
            slots = {item.slot: item.item_uuid for item in before.actors[identity].visual_loadout.layers}
            assert WeaponSlot.MELEE_MAIN.value not in slots
            assert slots[WeaponSlot.RANGED_MAIN.value] == bow
            assert any(item.item_uuid == sword for item in (before.actors[identity].controlled_items or ()))
        before = after
    assert saw_switch and sword_stored
