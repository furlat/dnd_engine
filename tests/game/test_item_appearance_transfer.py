"""Legal hand changes and item-owned materials survive native reset and replay."""

from dataclasses import replace
from uuid import UUID

import pygame
import pytest

from dnd.core.creature_types import DamageType
from dnd.blocks.appearance import AppearanceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_actions import AvailableActionsResult
from dnd.core.dice import AttackOutcome
from dnd.core.gridmap import LightLevel
from dnd.core.equipment_types import WeaponSlot, WeaponSet
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig
from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data, resolve_actor_layers, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.attack import select_attack_profile
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from dnd.runtime_reset import reset_engine_runtime
from game.controls import MenuState, handle_menu_event
from game.environment_draw import pick_environment_target
from game.item_draw import item_ground_commands
from game.player_facts import AttackFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from tests.game.item_appearance_scenarios import item_transfer_history, inventory_transfer_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def display():
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SDL_VIDEODRIVER", "dummy")
        env.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        try:
            yield pygame.display.set_mode((600, 400))
        finally:
            pygame.quit()


def test_coated_dagger_hand_floor_transfer_and_attack_replay(display):
    original, recipient, identity, history, floor_actions = item_transfer_history()
    state, roots = player_history(history, role="holder")
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    floor_actions = AvailableActionsResult.model_validate_json(floor_actions.model_dump_json())
    pickup_index = next(i for i, row in enumerate(floor_actions.all_actions) if row.behavior_id == "action.pick_up")
    pickup = floor_actions.all_actions[pickup_index]
    assert len({row.target_uuid for row in pickup.valid_targets if row.position == (3, 3)}) >= 2
    menu = MenuState(selected_action=pickup_index)
    camera = Camera(quadrant=0, zoom=1, viewport=display.get_size())
    choices = set()
    for _ in pickup.valid_targets:
        _, choice = handle_menu_event(menu, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
            floor_actions, camera, (), panel_rect=pygame.Rect(400, 0, 200, 400))
        choices.add(choice.target_indices)
        menu, _ = handle_menu_event(menu, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB),
            floor_actions, camera, (), panel_rect=pygame.Rect(400, 0, 200, 400))
    assert len(choices) == len(pickup.valid_targets)
    data = load_animation_data()
    saw_floor = saw_original_off = saw_recipient = saw_effect_change = False
    attacks = []
    for root in roots:
        state = reduce_lineage(state, root)
        for actor in state.actors.values():
            layers = resolve_player_layers(data, actor, rig_id=data.root_rig, active_weapon_set=WeaponSet.MELEE)
            for layer in layers:
                if layer.slot == "offhand" and layer.item_effects:
                    assert layer.category == "Offhand2" and layer.tint == 0x334455
                    saw_original_off |= actor.uuid == original
                    saw_recipient |= actor.uuid == recipient
                    saw_effect_change |= bool(layer.item_effects)
        if identity in state.objects:
            obj = state.objects[identity]
            if not obj.item.item_effects:
                continue
            if not saw_floor:
                camera = Camera(quadrant=0, zoom=1, viewport=display.get_size()).with_focus(obj.placement.position)
                catalog = load_catalog()
                sprite = item_ground_commands(obj, camera)[-1]
                opaque = next((x, y) for x in range(sprite.surface.width) for y in range(sprite.surface.height)
                              if sprite.surface.get_at((x, y)).a == 255)
                point = sprite.destination[0] + opaque[0], sprite.destination[1] + opaque[1]
                pixels = []
                for level in (LightLevel.BRIGHT_LIGHT, LightLevel.DIM_LIGHT):
                    senses = replace(state.senses, effective_light_levels=
                        {position: level for position in state.senses.effective_light_levels})
                    isolated = replace(state, objects={identity: obj}, senses=senses)
                    draw_frame(display, isolated, catalog, SurfaceCache(catalog), camera, 0, show_grid=False,
                        mouse_position=None, show_debug=False)
                    pixels.append(display.get_at(point)[:3])
                assert sum(pixels[1]) < sum(pixels[0])
            saw_floor = True
            assert obj.item.stack_count == 1 and obj.item.is_pickable
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=1, viewport=display.get_size()).with_focus(obj.placement.position)
                commands = item_ground_commands(obj, camera)
                assert commands and commands[-1].surface.get_bounding_rect().width > 0
                sprite = commands[-1]
                pixel = next((x, y) for x in range(sprite.surface.width) for y in range(sprite.surface.height)
                             if sprite.surface.get_at((x, y)).a > 0)
                point = sprite.destination[0]+pixel[0], sprite.destination[1]+pixel[1]
                assert pick_environment_target(point, {identity: obj}, camera) == identity
                assert item_ground_commands(obj, camera)[-1].destination == sprite.destination
        attacks.extend(node.fact for node in root.events if isinstance(node.fact, AttackFact))
    assert saw_floor and saw_original_off and saw_recipient and saw_effect_change
    attack, = attacks
    assert attack.source_item_uuid == identity
    assert any(effect.damage_type is DamageType.FIRE for effect in attack.item_effects)
    held = next(item for item in state.actors[recipient].visual_loadout.layers if item.item_uuid == identity)
    assert held.item_effects == ()
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("low_level", (False, True))
@pytest.mark.parametrize("hidden", (False, True))
def test_inventory_transfer_clears_previous_holder_without_revealing_hidden_receiver(low_level, hidden):
    giver, receiver, identity, history, legacy = inventory_transfer_history(low_level=low_level, hidden=hidden)
    assert all(item.item_uuid != identity for item in legacy.actors[giver].items)
    state, roots = player_history(history, role="giver")
    assert any(item.item_uuid == identity for item in state.actors[giver].controlled_items)
    for root in roots:
        state = reduce_lineage(state, root)
    assert all(item.item_uuid != identity for item in state.actors[giver].controlled_items)
    if hidden:
        assert receiver not in state.actors
    assert not Entity.get_all_entities()


@pytest.mark.parametrize("item_id", ("weapon.dagger", "weapon.shortsword", "weapon.scimitar", "weapon.handaxe", "weapon.club", "weapon.sickle"))
@pytest.mark.parametrize("body", ("NakedBody", "NakedBody2"))
def test_approved_offhand_families_keep_attack5_and_draw_actual_slot(display, item_id, body):
    reset_engine_runtime()
    identity = UUID(int=913)
    native = Entity.create(identity, "Offhand acceptance", config=EntityConfig(position=(3, 3),
        appearance=AppearanceConfig(body_category=body, has_beard=False)))
    weapon = build_authored_item(item_id, identity)
    native.install_initial_items(((weapon, None),))
    native.compose_entity()
    assert native.equip_item(weapon.uuid, WeaponSlot.MELEE_OFF)
    equipped = native.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)
    assert equipped is weapon
    item = equipped.to_item_presentation_state()
    data = load_animation_data()
    actor = ActorContact(str(identity), (3, 3), "S", 1)
    layers = resolve_actor_layers(data, AppearanceConfig(body_category=native.appearance.body_category, has_beard=False),
        (item,), ((WeaponSlot.MELEE_OFF.value, item.item_uuid),), WeaponSet.MELEE, rig_id=data.root_rig)
    assert any(layer.slot == "offhand" for layer in layers)
    fact = AttackFact(source_entity_uuid=identity, target_entity_uuid=UUID(int=914), behavior_id="action.attack",
        name="Attack", weapon_slot=WeaponSlot.MELEE_OFF, attack_outcome=AttackOutcome.HIT,
        damage_types=(DamageType.SLASHING, DamageType.FIRE), source_item_id=item_id)
    recipe = next(iter(data.attack_recipes.values()))
    profile = select_attack_profile(recipe, fact)
    assert profile.id == "melee-offhand" and profile.actor.clip == "Attack5"
    assert [(anchor.name, anchor.frame) for anchor in profile.anchors] == [("action_start", 0), ("contact", 8), ("recover", 10)]
    rows = load_actor_media(data, ((actor, layers, ("Attack5",)),))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=display.get_size()).with_focus(actor.grid)
        commands = actor_draw_commands(data, BodySample(str(identity), "Attack5", 8, "S"), actor, layers, rows, camera)
        assert commands and any(command.surface.get_bounding_rect().width for command in commands)
    reset_engine_runtime()
