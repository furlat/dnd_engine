"""Native wall casts: costs in, actual occupancy/damage/cleanup facts out.

Boundary: public spell execution, shared movement/reach and ordinary item damage.
No media, mocked collaborators or private ownership layout is part of acceptance.
"""

import pytest

from dnd.actions import Attack, AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageAppliedEvent, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.wall_constructions import FrigidAirZone, WallOfIce, WallOfIceZone, WallOfForce, WallOfForceZone, WallOfStone, WallOfStoneZone
from dnd.spells.wall_fields import WallOfThorns, WallOfThornsZone, WindWall, WindWallZone
from dnd.spells.transmutation import Disintegrate
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.spells.divination import SeeInvisibility
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import MovementMode
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


def scene(level, *, slots=None):
    reset_spell_regression_arena(24, 24)
    return create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots=slots or {level: 2})


def actor(position):
    return create_spell_regression_actor("Recipient", position, "monsters")


def cast(spell, caster, *, start=(5, 5), end=(9, 5), **fields):
    targets = [] if fields.get("wall_form") in {"ring", "dome"} else [end]
    with fixed_dice_faces(*([4] * 300)):
        result = spell(source_entity_uuid=caster.uuid, end_position=start,
            extra_target_positions=targets, **fields).apply()
    assert isinstance(result, SpellEvent) and not result.canceled, result
    return result


@pytest.mark.parametrize("success, expected", [(False, 28), (True, 14)])
def test_thorns_formation_and_contact_have_distinct_damage_types_and_saves(success, expected):
    caster = scene(6)
    target = actor((7, 5))
    force_save_result(target, "dexterity", succeeds=success)
    before = target.get_hp()
    cursor = EventQueue.event_cursor()
    cast(WallOfThorns, caster)
    assert before - target.get_hp() == expected
    with fixed_dice_faces(*([4] * 100)):
        target.on_turn_end()
    assert before - target.get_hp() == expected * 2
    packets = [e for _, e in EventQueue.iter_events_since(cursor)
               if isinstance(e, DamageAppliedEvent) and e.phase is EventPhase.COMPLETION]
    assert [e.damage_type for e in packets] == [DamageType.PIERCING, DamageType.SLASHING]
    assert get_map().is_blocking_optics(7, 5)
    assert get_map().can_reach_between((7, 3), (7, 7), PhysicalAccess.PROJECTILE, caster.uuid)


def test_thorns_movement_expenditure_survives_terrain_immunity_and_cleanup():
    caster = scene(6)
    grid = get_map()
    grid.set_tile(7, 5, tile=Tile.create((7, 5), walking_cost=2))
    cast(WallOfThorns, caster)
    assert grid.movement_edge_cost_units((7, 4), (7, 5), MovementMode.WALKING) == 5
    assert grid.movement_edge_cost_units((7, 4), (7, 5), MovementMode.WALKING,
                                        ignore_difficult_terrain=True) == 4
    owner = next(o for o in grid.get_spatial_conditions() if isinstance(o, WallOfThornsZone))
    owner.deactivate()
    assert grid.movement_edge_cost_units((7, 4), (7, 5), MovementMode.WALKING) == 2
    assert not grid.is_blocking_optics(7, 5)


def test_wind_path_formation_once_and_no_entry_or_turn_damage():
    caster = scene(3)
    target = actor((7, 5))
    force_save_result(target, "strength", succeeds=False)
    before = target.get_hp()
    with fixed_dice_faces(*([4] * 200)):
        result = WindWall(source_entity_uuid=caster.uuid, end_position=(5, 5),
            extra_target_positions=[(7, 5), (7, 7), (5, 7), (5, 5)]).apply()
    assert result is not None and not result.canceled
    assert before - target.get_hp() == 12
    Entity.update_entity_position(target, (7, 6))
    target.on_turn_end()
    assert before - target.get_hp() == 12
    assert not get_map().is_blocking_optics(7, 5)


@pytest.mark.parametrize("large", [False, True])
def test_wind_missile_deflection_spends_attack_and_large_missiles_pass(large):
    caster = scene(3)
    source = actor((7, 3))
    target = actor((7, 8))
    bow = build_authored_item("weapon.longbow", source.uuid)
    bow.missile_size = "large" if large else "ordinary"
    source.inventory.add_item(bow)
    assert source.equipment.equip(bow, WeaponSlot.RANGED_MAIN)
    cast(WindWall, caster)
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(19, 4):
        result = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN).apply()
    assert result is not None and not result.canceled
    assert source.action_economy.actions.normalized_score == 0
    assert (target.get_hp() < hp) is large
    if not large:
        assert result.attack_outcome is AttackOutcome.MISS
        assert result.intercepted_by_condition_uuid is not None
        assert result.projectile_deflection_position is not None


@pytest.mark.parametrize("size,gaseous,mode,blocked", [
    (Size.SMALL, False, MovementMode.FLYING, True),
    (Size.MEDIUM, False, MovementMode.FLYING, False),
    (Size.SMALL, False, MovementMode.WALKING, False),
    (Size.MEDIUM, True, MovementMode.WALKING, True),
])
def test_wind_selective_physical_passage(size, gaseous, mode, blocked):
    caster = scene(3)
    mover = actor((7, 4))
    mover.size = size
    mover.gaseous_body = gaseous
    cast(WindWall, caster)
    assert get_map().can_transition((7, 4), (7, 5), mover.uuid, mode) is not blocked


@pytest.mark.parametrize("spell, zone_type, opaque", [
    (WallOfIce, WallOfIceZone, False), (WallOfStone, WallOfStoneZone, True),
    (WallOfForce, WallOfForceZone, False),
])
def test_solid_panels_block_physical_crossings_with_independent_optics(spell, zone_type, opaque):
    caster = scene(spell.model_fields['spell_level'].default)
    cast(spell, caster)
    grid = get_map()
    zone = next(o for o in grid.get_spatial_conditions() if isinstance(o, zone_type))
    assert len(zone.sections) == 2
    assert not grid.can_transition((7, 4), (7, 5), caster.uuid)
    assert not grid.can_reach_between((7, 3), (7, 7), PhysicalAccess.PROJECTILE, caster.uuid)
    assert grid.is_blocking_optics(7, 5) is opaque
    zone.deactivate()
    assert grid.can_transition((7, 4), (7, 5), caster.uuid)
    assert not any(get_map().get_object_placement(identity) for identity in zone.sections)


def test_visible_force_wall_receives_normal_attack_without_becoming_damageable():
    caster = scene(5)
    targeter = create_spell_regression_actor('Attacker', (5, 4), 'monsters', spell_slots={2: 2})
    setup_standard_actions(targeter)
    cast(WallOfForce, caster)
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfForceZone))
    sections = tuple(zone.sections)
    Entity.update_all_entities_senses()
    assert not any(target.target_uuid in sections for row in get_available_actions(targeter).all_actions
        if row.behavior_id == 'action.attack' for target in row.valid_targets)
    seeing = SeeInvisibility(source_entity_uuid=targeter.uuid).apply()
    assert seeing is not None and not seeing.canceled
    targeter.on_turn_start()
    Entity.update_all_entities_senses()
    choice = next(((row, target) for row in get_available_actions(targeter).all_actions
        if row.template_name == f'Attack_{WeaponSlot.MELEE_MAIN.value}' for target in row.valid_targets
        if target.target_uuid in sections), None)
    assert choice is not None
    with fixed_dice_faces(19, 4):
        result = execute_available_action(targeter, *choice)
    assert isinstance(result, AttackEvent) and not result.canceled
    assert result.attack_outcome is AttackOutcome.HIT and result.total_damage == 0
    assert targeter.action_economy.actions.normalized_score == 0
    assert tuple(zone.sections) == sections
    assert all(BaseBlock.get(identity).health is None for identity in sections)
    assert not get_map().can_transition((5, 4), (5, 5), targeter.uuid)


def test_ice_section_breaks_locally_and_fridge_air_hurts_only_passage():
    caster = scene(6)
    cast(WallOfIce, caster)
    grid = get_map()
    zone = next(o for o in grid.get_spatial_conditions() if isinstance(o, WallOfIceZone))
    items = [BaseBlock.get(identity) for identity in zone.sections]
    items[0].receive_damage(15, DamageType.FIRE, caster.uuid)
    assert len(zone.sections) == 1
    assert items[1].get_hp() == 30
    assert len([o for o in grid.get_spatial_conditions() if isinstance(o, FrigidAirZone)]) == 1
    target = actor((5, 4))
    force_save_result(target, 'constitution', succeeds=False)
    hp = target.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([4] * 100)):
            Entity.update_entity_position(target, (5, 5))
            assert hp - target.get_hp() == 20
            target.on_turn_end()
            assert hp - target.get_hp() == 20
            Entity.update_entity_position(target, (5, 4))
            Entity.update_entity_position(target, (5, 5))
            assert hp - target.get_hp() == 20
    finally:
        EventQueue.end_turn_execution(turn)
    zone.deactivate()
    assert not grid.get_spatial_conditions()


def test_ice_dome_hollow_interior_shared_hp_and_complete_shatter():
    caster = scene(6)
    cast(WallOfIce, caster, start=(10, 10), wall_form='dome', displacement_side='outside')
    grid = get_map()
    zone = next(o for o in grid.get_spatial_conditions() if isinstance(o, WallOfIceZone))
    assert len(zone.sections) == 1
    item = BaseBlock.get(next(iter(zone.sections)))
    assert item.get_hp() == 120
    assert grid.can_transition((10, 10), (11, 10), caster.uuid)
    assert not grid.can_transition((11, 10), (12, 10), caster.uuid)
    assert grid.can_reach_between((10, 10), (11, 10), PhysicalAccess.PROJECTILE, caster.uuid)
    item.receive_damage(60, DamageType.FIRE, caster.uuid)
    assert not zone.sections
    assert grid.can_transition((11, 10), (12, 10), caster.uuid)
    air = next(o for o in grid.get_spatial_conditions() if isinstance(o, FrigidAirZone))
    target = actor((10, 10))
    hp = target.get_hp()
    Entity.update_entity_position(target, (11, 10))
    assert target.get_hp() == hp
    assert (10, 10) not in air.affected_positions


def test_ice_formation_displaces_then_damages_intersected_creature():
    caster = scene(6)
    target = actor((7, 5))
    force_save_result(target, 'dexterity', succeeds=False)
    hp = target.get_hp()
    cast(WallOfIce, caster)
    assert target.position == (7, 6)
    assert hp - target.get_hp() == 40


def test_stone_support_and_permanent_completion():
    caster = scene(5)
    cast(WallOfStone, caster)
    grid = get_map()
    zone = next(o for o in grid.get_spatial_conditions() if isinstance(o, WallOfStoneZone))
    identities = tuple(zone.sections)
    for _ in range(100):
        zone.progress()
    assert zone.permanent
    caster.remove_condition('Concentrating')
    assert all(BaseBlock.get(identity) is not None for identity in identities)
    assert not grid.can_transition((7, 4), (7, 5), caster.uuid)


def test_fridge_air_dome_crossing_into_interior_cell_still_hurts():
    caster = scene(6)
    cast(WallOfIce, caster, start=(10, 10), wall_form="dome", displacement_side="outside")
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfIceZone))
    BaseBlock.get(next(iter(zone.sections))).receive_damage(60, DamageType.FIRE, caster.uuid)
    target = actor((12, 11))
    force_save_result(target, "constitution", succeeds=False)
    hp = target.get_hp()
    with fixed_dice_faces(*([4] * 100)):
        Entity.update_entity_position(target, (11, 10))
    assert hp - target.get_hp() == 20


@pytest.mark.parametrize("succeeds", [True, False])
def test_stone_enclosure_escape_spends_reaction_not_normal_movement(succeeds):
    caster = scene(5)
    target = actor((7, 7))
    force_save_result(target, "dexterity", succeeds=succeeds)
    target.action_economy.consume("movement", target.action_economy.movement_remaining())
    result = WallOfStone(source_entity_uuid=caster.uuid, end_position=(5, 5),
        extra_target_positions=[(9, 5), (9, 9), (5, 9), (5, 5)]).apply()
    assert result is not None and not result.canceled
    assert (target.position != (7, 7)) is succeeds
    assert target.action_economy.reactions.normalized_score == (0 if succeeds else 1)
    assert target.action_economy.movement_remaining() == 0


def test_disintegrate_known_force_section_retires_complete_wall():
    caster = scene(5, slots={2: 2, 5: 2, 6: 2})
    result = SeeInvisibility(source_entity_uuid=caster.uuid).apply()
    assert result is not None and not result.canceled
    caster.action_economy.reset_all_costs()
    cast(WallOfForce, caster)
    caster.action_economy.reset_all_costs()
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfForceZone))
    identities = tuple(zone.sections)
    result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=identities[0]).apply()
    assert result is not None and not result.canceled, result
    assert not get_map().get_spatial_conditions()
    assert all(BaseBlock.get(identity) is None for identity in identities)
    assert get_map().can_transition((7, 4), (7, 5), caster.uuid)


def test_knowledge_of_force_wall_does_not_satisfy_disintegrate_sight():
    caster = scene(5, slots={5: 2, 6: 2})
    cast(WallOfForce, caster)
    caster.action_economy.reset_all_costs()
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfForceZone))
    identity = next(iter(zone.sections))
    result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=identity).apply()
    assert result is not None and result.canceled
    assert "can see" in result.status_message
    assert caster.action_economy.actions.normalized_score == 1
    assert zone.applied


def test_canceled_whole_wall_retirement_preserves_sections_and_blocking():
    caster = scene(6)
    cast(WallOfIce, caster)
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfIceZone))
    identities = tuple(zone.sections)
    handler = EventHandler(name="Refuse physical removal", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message="Removal refused"))
    EventQueue.add_event_handler(handler)
    assert not zone.deactivate()
    assert zone.applied and tuple(zone.sections) == identities
    assert all(BaseBlock.get(identity) is not None for identity in identities)
    assert not get_map().can_transition((7, 4), (7, 5), caster.uuid)
    EventQueue.remove_event_handler(handler)
    assert zone.deactivate()
    assert all(BaseBlock.get(identity) is None for identity in identities)


def test_refused_section_removal_does_not_create_a_gap_or_residual_air():
    caster = scene(6)
    cast(WallOfIce, caster)
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfIceZone))
    identity = next(iter(zone.sections))
    item = BaseBlock.get(identity)
    handler = EventHandler(name="Refuse broken section retirement", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message="Removal refused"))
    EventQueue.add_event_handler(handler)
    item.receive_damage(15, DamageType.FIRE, caster.uuid)
    assert identity in zone.sections and BaseBlock.get(identity) is item
    assert not any(isinstance(o, FrigidAirZone) for o in get_map().get_spatial_conditions())
    EventQueue.remove_event_handler(handler)
    item.retire()
    assert identity not in zone.sections
    assert any(isinstance(o, FrigidAirZone) for o in get_map().get_spatial_conditions())


def test_canceled_later_section_placement_leaves_no_created_sections():
    caster = scene(6)
    seen = []
    def refuse_second(event, _):
        if event.object_uuid not in seen:
            seen.append(event.object_uuid)
        return event.cancel(status_message="Second placement refused") if len(seen) == 2 else None
    handler = EventHandler(name="Refuse second panel", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED, event_phase=EventPhase.EFFECT)],
        event_processor=refuse_second)
    EventQueue.add_event_handler(handler)
    result = WallOfIce(source_entity_uuid=caster.uuid, end_position=(5, 5), extra_target_positions=[(9, 5)]).apply()
    assert result is not None and result.canceled
    assert len(seen) == 2 and all(BaseBlock.get(identity) is None for identity in seen)
    assert not get_map().get_spatial_conditions()
    assert get_map().can_transition((7, 4), (7, 5), caster.uuid)


@pytest.mark.parametrize("spell, end", [(WallOfIce, (7, 7)), (WallOfStone, (7, 7)), (WindWall, (5, 5))])
def test_invalid_shapes_reject_without_spending(spell, end):
    level = spell.model_fields["spell_level"].default
    caster = scene(level)
    result = spell(source_entity_uuid=caster.uuid, end_position=(5, 5), extra_target_positions=[end]).apply()
    assert result is None or result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert not get_map().get_spatial_conditions()


def test_wind_has_no_interception_in_globe_excluded_cells():
    caster = scene(3)
    owner = create_spell_regression_actor("Globe owner", (7, 5), "heroes", spell_slots={6: 2})
    result = GlobeOfInvulnerability(source_entity_uuid=owner.uuid).apply()
    assert result is not None and not result.canceled
    cast(WindWall, caster, end=(13, 5))
    grid = get_map()
    assert grid.missile_interceptor((7, 4), (7, 6), "ordinary") is None
    assert grid.missile_interceptor((12, 4), (12, 6), "ordinary") is not None


def test_expiry_after_vetoed_break_removes_wall_without_creating_air():
    caster = scene(6)
    cast(WallOfIce, caster)
    zone = next(o for o in get_map().get_spatial_conditions() if isinstance(o, WallOfIceZone))
    identities = tuple(zone.sections)
    handler = EventHandler(name="Refuse break removal", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message="Removal refused"))
    EventQueue.add_event_handler(handler)
    BaseBlock.get(identities[0]).receive_damage(15, DamageType.FIRE, caster.uuid)
    EventQueue.remove_event_handler(handler)
    assert zone.deactivate()
    assert all(BaseBlock.get(identity) is None for identity in identities)
    assert not get_map().get_spatial_conditions()


@pytest.mark.parametrize("identity, magical", [("gear.holy_symbol", False),
                                             ("weapon.circus.longsword_plus_one", True),
                                             ("consumable.potion_true_seeing", True)])
def test_disintegrate_ordinary_object_without_destroying_magic_item(identity, magical):
    caster = scene(6)
    item = build_authored_item(identity, caster.uuid)
    item.place_on_grid((3, 2))
    Entity.update_all_entities_senses()
    result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None
    assert result.canceled is magical
    assert (BaseBlock.get(item.uuid) is not None) is magical
