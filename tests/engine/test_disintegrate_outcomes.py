"""Actual Disintegrate commands retain dust only after accepted lethal damage."""
import pytest

from dnd.actions import SpellEvent
from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DeathEvent, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent, TakeDamageEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.entity import Entity, EntityConfig
from dnd.items.environment_interactables import StorageChest
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import Disintegrate
from dnd.spells.wall_constructions import WallOfStone, WallOfStoneZone, WallSection, WallOfForce, WallOfForceZone, WallOfIce, FrigidAirZone
from dnd.spells.divination import SeeInvisibility
from dnd.types.materials import Material
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


@pytest.fixture
def scene():
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor('Caster', (2, 4), 'heroes', spell_slots={2: 2, 5: 2, 6: 8, 7: 2, 8: 2, 9: 2})
    target = create_spell_regression_actor('Target', (7, 4), 'monsters')
    force_save_result(target, 'dexterity', succeeds=False)
    Entity.update_all_entities_senses(max_distance=100)
    yield caster, target
    reset_engine_runtime()


def cast(caster, target, slot=6):
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 100)):
        result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, cast_at_level=slot).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    return result, [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize('slot', [6, 7, 8, 9])
def test_survivor_receives_one_correct_scaled_packet_without_dust(scene, slot):
    caster, target = scene
    before = target.get_normal_hp()
    result, events = cast(caster, target, slot)
    assert before - target.get_normal_hp() == 40 + 4 * (10 + 3 * (slot - 6))
    assert result.total_damage == before - target.get_normal_hp()
    packet, = (event for event in events if isinstance(event, TakeDamageEvent))
    assert packet.damage_rolls[0].effective_dice_count == 10 + 3 * (slot - 6)
    assert packet.effect_origin == result.to_effect_origin()
    assert target.health.remains_disposition is RemainsDisposition.INTACT
    assert not any(isinstance(event, DeathEvent) for event in events)


def test_lethal_ray_disintegrates_death_save_actor_preserving_nested_magic_items(scene):
    caster, target = scene
    target.uses_death_saves = True
    set_hp(target, 70)
    weapon = build_authored_item('weapon.dagger', target.uuid)
    assert target.loot_item(weapon) and target.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    chest = StorageChest(source_entity_uuid=target.uuid, item_id='test.carried_chest', is_pickable=True)
    assert target.loot_item(chest)
    magic = build_authored_item('weapon.circus.longsword_plus_one', target.uuid)
    ordinary = build_authored_item('gear.holy_symbol', target.uuid)
    assert chest.chest_inventory.add_item(magic)
    assert chest.chest_inventory.add_item(ordinary)
    _, events = cast(caster, target)
    assert target.health.life_state is LifeState.DEAD
    assert target.health.remains_disposition is RemainsDisposition.DISINTEGRATED
    assert not target.revive()
    death, = (event for event in events if isinstance(event, DeathEvent))
    assert death.remains_disposition is RemainsDisposition.DISINTEGRATED
    assert DeathEvent.model_validate_json(death.model_dump_json(), context=PASSIVE_EVENT_REPLAY).remains_disposition is RemainsDisposition.DISINTEGRATED
    assert set(death.destroyed_item_uuids) == {weapon.uuid, ordinary.uuid, chest.uuid}
    assert death.preserved_item_uuids == (magic.uuid,)
    assert all(BaseBlock.get(item.uuid) is None for item in (weapon, ordinary, chest))
    assert BaseBlock.get(magic.uuid) is magic and magic.is_magical
    assert get_map().get_object_position(magic.uuid) == target.position
    assert magic.owner_uuid is None and magic.stored_in_uuid is None
    assert target.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is None
    dust = [event for event in events if isinstance(event, ItemDestructionEvent)]
    assert {event.item_uuid for event in dust} == set(death.destroyed_item_uuids)
    assert all(event.remains_disposition is RemainsDisposition.DISINTEGRATED for event in dust)


@pytest.mark.parametrize('veto', [EventType.DEATH, EventType.TAKE_DAMAGE])
def test_vetoed_lethal_outcome_never_destroys_body_or_gear(scene, veto):
    caster, target = scene
    set_hp(target, 10)
    item = build_authored_item('weapon.dagger', target.uuid)
    assert target.loot_item(item)
    handler = EventHandler(source_entity_uuid=target.uuid, name='Preserve target',
        trigger_conditions=[Trigger(event_type=veto, event_phase=EventPhase.EXECUTION)],
        event_processor=lambda event, _: event.cancel(status_message='Preserved'))
    EventQueue.add_event_handler(handler)
    _, events = cast(caster, target)
    assert target.health.life_state is LifeState.ALIVE
    assert target.get_normal_hp() >= 1
    assert target.health.remains_disposition is RemainsDisposition.INTACT
    assert target.inventory.has_item(item.uuid) and BaseBlock.get(item.uuid) is item
    assert not any(isinstance(event, ItemDestructionEvent) for event in events)
    assert not any(isinstance(event, DeathEvent) and not event.canceled for event in events)


@pytest.mark.parametrize('protection', ['temporary_hp', 'resistance', 'damage_cap'])
def test_native_defenses_that_preserve_normal_hp_prevent_dust(scene, protection):
    caster, target = scene
    set_hp(target, 70)
    if protection == 'temporary_hp':
        target.health.add_temporary_hit_points(20, target.uuid)
    elif protection == 'resistance':
        target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
            name='Force resistance', damage_type=DamageType.FORCE, value=ResistanceStatus.RESISTANCE))
    else:
        EventQueue.add_event_handler(EventHandler(source_entity_uuid=target.uuid, name='Preserve one HP',
            trigger_conditions=[Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EFFECT)],
            event_processor=lambda event, _: event.with_updates(normal_hit_point_damage_cap=69)))
    _, events = cast(caster, target)
    assert target.health.life_state is LifeState.ALIVE and target.get_normal_hp() > 0
    assert target.health.remains_disposition is RemainsDisposition.INTACT
    assert not any(isinstance(event, DeathEvent) for event in events)


@pytest.mark.parametrize('height', [2, 4])
def test_large_object_keeps_identity_outside_exact_cube_and_preserves_cuts_when_moved(scene, height):
    caster, _ = scene
    item = WorldItem(source_entity_uuid=caster.uuid, item_id='test.large_statue', name='Large statue',
        health=BaseItem.create_item_health(caster.uuid, 200), is_targetable=True,
        blocks_movement=True, blocks_optics_field=True, blocks_propagation_field=True,
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
            vertical_extent_steps=height, footprint_offsets=tuple((x, y) for x in range(4) for y in range(3))))
    item.place_on_grid((5, 4))
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, item)
    assert BaseBlock.get(item.uuid) is item and item.is_active
    placement = get_map().get_object_placement(item.uuid)
    assert placement is not None and placement.object_uuid == item.uuid
    cut, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert cut.affected_volume is not None and cut.resulting_placement == placement
    restored = ItemDestructionEvent.model_validate_json(cut.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    assert restored.affected_volume == cut.affected_volume and restored.resulting_placement == placement
    assert set(placement.removed_bands) == {(x, y, z) for x in (5, 6) for y in (4, 5) for z in (0, 1)}
    assert item.uuid not in get_map().get_center_objects_at((5, 4), 0)
    assert item.uuid in get_map().get_center_objects_at((8, 4), 0)
    if height == 4:
        assert item.uuid in get_map().get_center_objects_at((5, 4), 2)
    get_map().remove_object(item.uuid)
    item.place_on_grid((10, 4))
    assert item.uuid not in get_map().get_center_objects_at((10, 4), 0)
    assert item.uuid in get_map().get_center_objects_at((13, 4), 0)


def test_twenty_foot_stone_panel_retains_owner_and_only_opens_affected_cube(scene):
    caster, _ = scene
    for tile in get_map().get_all_tiles().values():
        tile.surface = tile.surface.model_copy(update={"base_material": Material.STONE})
    result = WallOfStone(source_entity_uuid=caster.uuid, end_position=(5, 6),
        extra_target_positions=[(9, 6)], stone_panel_width_feet=20).apply()
    assert result is not None and not result.canceled
    zone, = (condition for condition in get_map().get_spatial_conditions() if isinstance(condition, WallOfStoneZone))
    identity, = zone.sections
    item = BaseBlock.get(identity)
    assert isinstance(item, WallSection)
    assert not get_map().can_transition((5, 5), (5, 6), caster.uuid)
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, item)
    assert BaseBlock.get(identity) is item and identity in zone.sections and zone.applied
    assert len(item.geometry.removed_sections) == 1
    assert get_map().can_transition((5, 5), (5, 6), caster.uuid)
    assert not get_map().can_transition((9, 5), (9, 6), caster.uuid)
    cut, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert cut.affected_volume == item.geometry.removed_sections[0]
    assert cut.resulting_state is not None and cut.resulting_state.construction_geometry == item.geometry


def test_repeated_cuts_finish_tall_object_without_regrowing_lower_bands(scene):
    caster, _ = scene
    item = WorldItem(source_entity_uuid=caster.uuid, item_id='test.tall_pillar', name='Tall pillar',
        is_targetable=True, blocks_movement=True,
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
            vertical_extent_steps=4))
    item.place_on_grid((5, 4))
    Entity.update_all_entities_senses(max_distance=100)
    cast(caster, item)
    assert BaseBlock.get(item.uuid) is item
    assert item.uuid not in get_map().get_center_objects_at((5, 4), 0)
    assert item.uuid in get_map().get_center_objects_at((5, 4), 2)
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, item)
    assert BaseBlock.get(item.uuid) is None
    assert not get_map().get_center_objects_at((5, 4), 2)
    destruction, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert destruction.destroyed_item_uuids == (item.uuid,)
    assert destruction.resulting_state is None


def test_targeted_container_spills_its_untargeted_contents_without_orphaning_them(scene):
    caster, _ = scene
    chest = StorageChest(source_entity_uuid=caster.uuid, item_id='test.targeted_chest', is_targetable=True)
    chest.place_on_grid((5, 4))
    items = [build_authored_item(identity, caster.uuid) for identity in
             ('weapon.dagger', 'weapon.circus.longsword_plus_one')]
    for item in items:
        assert chest.chest_inventory.add_item(item)
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, chest)
    assert BaseBlock.get(chest.uuid) is None
    assert all(BaseBlock.get(item.uuid) is item and get_map().get_object_position(item.uuid) == (5, 4) for item in items)
    destruction, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert set(destruction.preserved_item_uuids) == {item.uuid for item in items}


def test_force_creation_commits_one_explicit_outcome_for_every_removed_section(scene):
    caster, _ = scene
    sight = SeeInvisibility(source_entity_uuid=caster.uuid).apply()
    assert sight is not None and not sight.canceled
    caster.action_economy.reset_all_costs()
    result = WallOfForce(source_entity_uuid=caster.uuid, end_position=(5, 6), extra_target_positions=[(9, 6)]).apply()
    assert result is not None and not result.canceled
    zone, = (condition for condition in get_map().get_spatial_conditions() if isinstance(condition, WallOfForceZone))
    identities = set(zone.sections)
    item = BaseBlock.get(next(iter(identities)))
    assert isinstance(item, WallSection)
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, item)
    destruction, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert set(destruction.destroyed_item_uuids) == identities
    assert destruction.remains_disposition is RemainsDisposition.DISINTEGRATED
    assert not zone.applied and all(BaseBlock.get(identity) is None for identity in identities)


def test_partial_ice_dome_keeps_unhit_shell_and_leaves_only_cut_air(scene):
    caster, _ = scene
    result = WallOfIce(source_entity_uuid=caster.uuid, end_position=(6, 6), wall_form='dome',
        dome_radius_feet=10, displacement_side='outside').apply()
    assert result is not None and not result.canceled
    item, = (item for item in BaseItem.get_all_items() if isinstance(item, WallSection))
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=100)
    _, events = cast(caster, item)
    destruction, = (event for event in events if isinstance(event, ItemDestructionEvent))
    assert destruction.affected_volume is not None and BaseBlock.get(item.uuid) is item
    air, = (condition for condition in get_map().get_spatial_conditions() if isinstance(condition, FrigidAirZone))
    assert air.affected_positions
    assert all(destruction.affected_volume.contains_band(position, item.geometry.base_height_steps)
               for position in air.affected_positions)


def test_ordinary_dead_body_still_revives(scene):
    caster, target = scene
    set_hp(target, 5)
    target.receive_damage(10, DamageType.FORCE, caster.uuid)
    assert target.health.life_state is LifeState.DEAD
    assert target.health.remains_disposition is RemainsDisposition.INTACT
    assert target.revive(hit_points=2)
    assert target.health.life_state is LifeState.ALIVE and target.get_normal_hp() == 2


def test_rejected_section_change_preserves_entire_object_and_has_no_committed_dust(scene):
    caster, _ = scene
    item = WorldItem(source_entity_uuid=caster.uuid, item_id='test.vetoed_wall', name='Vetoed wall',
        is_targetable=True, blocks_movement=True,
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
            vertical_extent_steps=2, footprint_offsets=((0, 0), (1, 0), (2, 0), (3, 0))))
    item.place_on_grid((5, 4))
    Entity.update_all_entities_senses(max_distance=100)
    before = get_map().get_object_placement(item.uuid)
    handler = EventHandler(source_entity_uuid=caster.uuid, name='Refuse geometry change',
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_CHANGED, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message='Preserve geometry'))
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None and result.canceled
    assert get_map().get_object_placement(item.uuid) == before
    assert item.removed_local_bands == ()
    assert not any(isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION and not event.canceled
                   for _, event in EventQueue.iter_events_since(cursor))


def test_post_commit_death_observer_cannot_rewrite_an_accepted_dust_fact(scene):
    caster, target = scene
    set_hp(target, 10)
    EventQueue.add_event_handler(EventHandler(source_entity_uuid=target.uuid, name='Late death observer',
        trigger_conditions=[Trigger(event_type=EventType.DEATH, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message='Too late to veto committed death')))
    _, events = cast(caster, target)
    death, = (event for event in events if isinstance(event, DeathEvent))
    assert not death.canceled and death.remains_disposition is RemainsDisposition.DISINTEGRATED
    assert target.health.life_state is LifeState.DEAD
    assert target.health.remains_disposition is RemainsDisposition.DISINTEGRATED


def test_configured_dust_remains_keep_the_native_revival_restriction(scene):
    caster, _ = scene
    dust = Entity.create(source_entity_uuid=caster.uuid, name='Recorded dust', config=EntityConfig(
        health=HealthConfig(life_state=LifeState.DEAD, remains_disposition=RemainsDisposition.DISINTEGRATED)))
    assert dust.health.remains_disposition is RemainsDisposition.DISINTEGRATED
    assert dust.health.life_state is LifeState.DEAD and not dust.revive()
