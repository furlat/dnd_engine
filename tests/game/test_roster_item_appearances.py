"""Authored roster gear keeps native rules and renders through existing slots/media."""

from dataclasses import replace
from uuid import uuid4

from PIL import Image
import pygame
import pytest

from dnd.blocks.appearance import AppearanceConfig
from dnd.content.items.authored_item_builders import materialize_item_definition, build_authored_item
from dnd.blocks.equipment import EquipmentConfig, Equipment
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS, AUTHORED_WEARABLE_DEFINITIONS
from dnd.content.items.roster_item_definitions import ROSTER_CARRIED_DEFINITIONS, ROSTER_GEAR_DEFINITIONS, ROSTER_MAUL_DEFINITION
from dnd.core.equipment_types import BodyPart, WeaponSet, WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.core.gridmap import get_map
from dnd.items.authored_variant_inventory import AUTHORED_ITEM_VARIANT_CATEGORIES, AuthoredItemVariantCategory
from dnd.runtime_reset import reset_engine_runtime
from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data, resolve_actor_layers, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.item_appearance import ground_appearance
from game.item_draw import item_ground_commands
from dnd.core.events import WorldObjectState
from game.player_reduction import reduce_lineage
from tests.game.item_appearance_scenarios import item_transfer_history
from tests.game.player_helpers import player_history
from game.projection import Camera


ROWS = tuple((category, row) for category in AUTHORED_ITEM_VARIANT_CATEGORIES
             for row in category.variants if "roster-derived" in row.tags)
DEFINITIONS = {ROSTER_MAUL_DEFINITION.item_id: ROSTER_MAUL_DEFINITION, **AUTHORED_WEAPON_DEFINITIONS, **AUTHORED_WEARABLE_DEFINITIONS, **ROSTER_CARRIED_DEFINITIONS, **ROSTER_GEAR_DEFINITIONS}


def selected_definition(category, row):
    item_id = category.mechanical_factory_identity.split(":item:")[1].split("@")[0]
    base = DEFINITIONS[item_id]
    return replace(base, visual_item_name=category.base_category, visual_variant_id=row.visual_variant_id)


def test_all_admitted_appearances_have_full_original_action_and_ground_media():
    data = load_animation_data()
    rig = data.rigs[data.root_rig]
    clips = tuple(name for name, clip in rig.clips.items() if "NakedBody" in clip.sheets)
    checked = set()
    for category, row in ROWS:
        ground = ground_appearance(category.base_category, row.visual_variant_id)
        assert ground is not None
        assert tuple(sorted(ground.layers, key=lambda r: r.render_layer.value)) == row.equipment_layers
        definition = selected_definition(category, row)
        item = materialize_item_definition(definition, uuid4())
        equipment = Equipment.create(source_entity_uuid=uuid4(), config=EquipmentConfig(
            one_handed_offhand_grants={uuid4()}))
        for slot in equipment.compatible_slots_for_actor(item):
            layers = resolve_actor_layers(data, AppearanceConfig(), (item.snapshot_item_state(),),
                                          ((slot.value, item.uuid),), WeaponSet.RANGED if slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE,
                                          rig_id=data.root_rig)
            assert any(layer.item_uuid == item.uuid for layer in layers)
            for layer in layers:
                for clip in clips:
                    url = rig.clips[clip].sheets[layer.category]
                    path = data.resources[url]
                    assert path.is_file(), (category.base_category, row.visual_variant_id, slot, clip, path)
                    if path not in checked:
                        with Image.open(path) as sheet:
                            assert sheet.size == (rig.cell_width * rig.clips[clip].frames, rig.cell_height * 8)
                        checked.add(path)
        assert ground.shadow_sprite_key == "Shadow" and ground.reference_tile_width == 64
    assert ROWS and checked


def test_partial_garment_anchor_is_explicit_and_invalid_layers_still_fail():
    category = next(c for c in AUTHORED_ITEM_VARIANT_CATEGORIES if c.base_category == "Common Clothes")
    partials = [r for r in category.variants if r.registration_render_layer is not None]
    assert partials
    for row in partials:
        assert row.registration_render_layer is not None
        assert row.registration_render_layer.value == "legs"
        assert {r.render_layer.value for r in row.equipment_layers} == {"legs", "belt"}
        invalid = category.model_dump(mode="json")
        invalid["variants"] = [row.model_dump(mode="json")]
        invalid["allowed_registration_layers"] = []
        with pytest.raises(ValueError, match="not declared"):
            AuthoredItemVariantCategory.model_validate(invalid)
        invalid["allowed_registration_layers"] = ["chest", "legs"]
        invalid["variants"][0]["equipment_layers"] = [r for r in invalid["variants"][0]["equipment_layers"] if r["render_layer"] != "legs"]
        with pytest.raises(ValueError, match="exactly one primary"):
            AuthoredItemVariantCategory.model_validate(invalid)


@pytest.mark.parametrize("body", ["NakedBody", "NakedBody2"])
def test_cloak_and_waist_render_on_body_and_floor_without_fake_chest(monkeypatch, body):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    reset_engine_runtime(grid_size=(8, 5))
    pygame.init()
    game = Game()
    try:
        pygame.display.set_mode((600, 400))
        actor = Entity.create(uuid4(), "Wearer", config=EntityConfig(position=(2, 2), appearance=AppearanceConfig(body_category=body)))
        waist_category, waist = next((c, r) for c, r in ROWS if r.registration_render_layer is not None)
        cloak_category, cloak = next((c, r) for c, r in ROWS if c.base_category == "Cloak")
        clothes = materialize_item_definition(selected_definition(waist_category, waist), actor.uuid)
        cape = materialize_item_definition(selected_definition(cloak_category, cloak), actor.uuid)
        actor.install_initial_items(((clothes, BodyPart.BODY), (cape, BodyPart.CLOAK)))
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        assert not cape.item_properties and not cape.is_magical
        assert actor.ac_bonus().normalized_score == 10
        data = load_animation_data()
        layers = resolve_actor_layers(data, AppearanceConfig(body_category=body), (clothes.snapshot_item_state(), cape.snapshot_item_state()),
                                      ((BodyPart.BODY.value, clothes.uuid), (BodyPart.CLOAK.value, cape.uuid)), WeaponSet.NONE, rig_id=data.root_rig)
        assert "chest" not in {layer.slot for layer in layers}
        assert next(layer for layer in layers if layer.slot == "cloak").item_uuid == cape.uuid
        contact = ActorContact(str(actor.uuid), (2, 2), "S", 1)
        rows = {}
        for clip in ("Idle", "Run", "Attack1", "TakeDamage", "Die"):
            media = load_actor_media(data, ((contact, layers, (clip,)),), body_rows=rows)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=1, viewport=(600, 400))
                drawn = actor_draw_commands(data, BodySample(str(actor.uuid), clip, 0, "S"), contact, layers, media, camera)
                assert drawn and all(command.surface.get_bounding_rect().width for command in drawn)
            rows.clear()
        for item in (clothes, cape):
            slot = item.default_equipment_slot()
            assert slot is not None
            assert actor.unequip_item(slot) is item
            assert actor.drop_item(item.uuid) is item
            placement = get_map().get_object_placement(item.uuid)
            assert placement is not None
            obj = WorldObjectState(item=item.snapshot_item_state(), placement=placement)
            for quadrant in range(4):
                commands = item_ground_commands(obj, Camera(quadrant=quadrant, zoom=1, viewport=(600, 400)))
                assert len(commands) == 2 and commands[-1].surface.get_bounding_rect().width
    finally:
        game.close()
        reset_engine_runtime()
        pygame.quit()


@pytest.mark.parametrize("backpack", (False, True))
def test_selected_sword_and_outfit_transfer_only_through_received_events(backpack):
    from_holder = "holder"
    original, recipient, sword, history, _ = item_transfer_history(
        include_floor_robe=False, roster_outfit=True, roster_backpack=backpack, drop_position=(3, 4))
    assert not Entity.get_all_entities()
    data = load_animation_data()
    states = {}
    seen_floor = set()
    for role in (from_holder, "recipient"):
        state, roots = player_history(history, role=role)
        for root in roots:
            state = reduce_lineage(state, root)
            for obj in state.objects.values():
                if obj.item.visual_item_name == "Quiver" or (obj.item.visual_variant_id and obj.item.visual_variant_id.startswith("roster.")):
                    seen_floor.add(obj.item.item_uuid)
                    assert ground_appearance(obj.item.visual_item_name, obj.item.visual_variant_id) is not None
            for actor in state.actors.values():
                resolve_player_layers(data, actor, rig_id=data.root_rig)
        states[role] = state
    assert len(seen_floor) == 3 + int(backpack) and sword in seen_floor
    for state in states.values():
        assert not seen_floor.intersection(state.objects)
        held = state.actors[recipient].visual_loadout.layers
        assert {row.item_uuid for row in held} == seen_floor
        layers = resolve_player_layers(data, state.actors[recipient], rig_id=data.root_rig)
        assert {layer.slot for layer in layers} == ({"shadow", "body", "legs", "belt", "cloak", "offhand"}
                                                  | ({"backpack"} if backpack else set()))
        if backpack:
            assert next(layer for layer in layers if layer.slot == "cloak").item_uuid != next(
                layer for layer in layers if layer.slot == "backpack").item_uuid
        assert next(layer for layer in layers if layer.slot == "body").category == "NakedBody2"
        assert not state.actors[original].visual_loadout.layers


def test_talented_longsword_keeps_one_identity_in_both_hands_and_on_ground():
    reset_engine_runtime(grid_size=(6, 5))
    game = Game()
    try:
        holder = Entity.create(uuid4(), "Swordsman", config=EntityConfig(
            equipment=EquipmentConfig(one_handed_offhand_grants={uuid4()})))
        sword = build_authored_item("weapon.longsword", holder.uuid)
        sword.visual_variant_id = "roster.0b5b0e9f7dae"
        holder.install_initial_items(((sword, WeaponSlot.MELEE_OFF),))
        holder.compose_entity()
        game.deploy_entity(holder, (2, 2))
        data = load_animation_data()
        for slot, key in ((WeaponSlot.MELEE_OFF, "Offhand1"), (WeaponSlot.MELEE_MAIN, "Melee2")):
            if slot is WeaponSlot.MELEE_MAIN:
                assert holder.unequip_item(WeaponSlot.MELEE_OFF) is sword
                assert holder.equip_item(sword.uuid, slot)
            layers = resolve_actor_layers(data, AppearanceConfig(), (sword.snapshot_item_state(),),
                ((slot.value, sword.uuid),), WeaponSet.MELEE, rig_id=data.root_rig)
            weapon_layers = [layer for layer in layers if layer.item_uuid == sword.uuid]
            assert len(weapon_layers) == 1
            assert weapon_layers[0].category == key
            for clip in ("Idle", "Attack1", "TakeDamage", "Die"):
                assert data.resources[data.rigs[data.root_rig].clips[clip].sheets[key]].is_file()
        floor = ground_appearance("Longsword", sword.visual_variant_id)
        assert floor is not None and floor.tint == 12039858
    finally:
        game.close()
        reset_engine_runtime(grid_size=(6, 5))


def test_all_authored_one_handed_categories_support_talented_offhand():
    data = load_animation_data()
    equipment = Equipment.create(source_entity_uuid=uuid4(), config=EquipmentConfig(
        one_handed_offhand_grants={uuid4()}))
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES:
        if category.mechanical_factory_identity is None:
            continue
        item_id = category.mechanical_factory_identity.split(":item:")[1].split("@")[0]
        weapons = {**AUTHORED_WEAPON_DEFINITIONS, **ROSTER_CARRIED_DEFINITIONS}
        if item_id not in weapons:
            continue
        definition = replace(weapons[item_id], visual_item_name=category.base_category)
        item = materialize_item_definition(definition, uuid4())
        if WeaponSlot.MELEE_OFF not in equipment.compatible_slots_for_actor(item):
            continue
        for variant in (None, *(row.visual_variant_id for row in category.variants)):
            state = item.snapshot_item_state().model_copy(update={"visual_variant_id": variant})
            layers = resolve_actor_layers(data, AppearanceConfig(), (state,),
                ((WeaponSlot.MELEE_OFF.value, item.uuid),), WeaponSet.MELEE, rig_id=data.root_rig)
            owned = [layer for layer in layers if layer.item_uuid == item.uuid]
            assert len(owned) == 1 and owned[0].slot == "offhand", (category.base_category, variant)
            for clip in data.rigs[data.root_rig].clips.values():
                if "NakedBody" in clip.sheets:
                    assert data.resources[clip.sheets[owned[0].category]].is_file()
