"""Antimagic gates native contributions without reapplying their owners."""
from uuid import uuid4

import pytest

from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType, ConditionTag
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.effect_types import AntimagicException
from dnd.types.world import MovementMode
from dnd.conditions import Invisible
from dnd.core.base_block import SensesType
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSlot, WeaponProperty
from dnd.blocks.equipment import Weapon
from dnd.core.creature_types import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.events import Range, RangeType
from dnd.core.dice import fixed_dice_faces
from dnd.actions import Attack
from dnd.conditions import Hidden
from dnd.conditions import Poisoned
from dnd.spells.wall_constructions import WallOfForce, WallOfForceZone, WallOfStone, WallOfStoneZone
from dnd.types.physical_access import PhysicalAccess
from dnd.spells.abjuration import AntimagicField, AntimagicFieldZone
from dnd.spells.transmutation import HasteEffect, Telekinesis
from dnd.spells.transmutation import DarkvisionEffect
from dnd.spells.conjuration import GreaseZone, HeroesFeastSource, MistyStep, GuardianOfFaith, GuardianOfFaithZone
from dnd.entity import Entity
from dnd.core.base_block import BaseBlock
from tests.engine.test_summoning_lifecycle import battle, cast_one
from tests.engine.test_roster_support_spells import game, actor, cast


def test_structural_item_immunity_source_is_not_mistaken_for_a_condition(game):
    target = actor(game)
    item = build_authored_item('environment.furniture.clay_stove', source_entity_uuid=target.uuid)
    target.add_condition_immunity_source('Poisoned', item.uuid)
    poisoned = Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(poisoned)
    assert 'Poisoned' not in target.active_conditions
    assert target.remove_condition_immunity_source('Poisoned', item.uuid)
    target.add_condition(Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    assert 'Poisoned' in target.active_conditions


def test_antimagic_retains_effect_and_owned_ids_while_clock_expires(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    haste = HasteEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, tags={ConditionTag.MAGICAL},
        duration=Duration(duration_type=DurationType.ROUNDS, duration=2))
    target.add_condition(haste)
    owned = dict(haste.modifers_uuids), tuple(haste.event_handlers_uuids)
    cast(AntimagicField, caster)
    assert target.active_conditions_by_uuid[haste.uuid] is haste and haste.applied
    assert (haste.modifers_uuids, tuple(haste.event_handlers_uuids)) == owned
    assert target.action_economy.current_speed() == 30
    assert not target.action_economy.get_restricted_action_grants()
    target.on_turn_start(round_number=1)
    assert haste.duration.duration == 1
    target.on_turn_start(round_number=2)
    assert haste.uuid not in target.active_conditions_by_uuid
    caster.remove_condition('Concentrating')
    assert haste.uuid not in target.active_conditions_by_uuid


def test_overlapping_fields_restore_only_after_last_provider_without_reapplication(game):
    first, second = actor(game), actor(game, 'Second', (4, 3))
    target = actor(game, 'Recipient', (3, 2))
    haste = HasteEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, tags={ConditionTag.MAGICAL})
    target.add_condition(haste)
    cast(AntimagicField, first)
    cast(AntimagicField, second)
    assert target.action_economy.current_speed() == 30
    cursor = EventQueue.event_cursor()
    first.remove_condition('Concentrating')
    assert target.action_economy.current_speed() == 30
    second.remove_condition('Concentrating')
    assert target.active_conditions_by_uuid[haste.uuid] is haste
    assert target.action_economy.current_speed() == 60
    assert not [event for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.CONDITION_APPLICATION and event.phase is EventPhase.COMPLETION]


def test_invisibility_and_owned_sense_resume(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    invisible = Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL})
    vision = DarkvisionEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL})
    target.add_condition(invisible)
    target.add_condition(vision)
    assert target.is_invisible and target.senses.get_sense_range(SensesType.DARKVISION) == 60
    cast(AntimagicField, caster)
    assert not target.is_invisible and target.senses.get_sense_range(SensesType.DARKVISION) == -1
    assert invisible.applied and vision.applied
    caster.remove_condition('Concentrating')
    assert target.is_invisible and target.senses.get_sense_range(SensesType.DARKVISION) == 60


def test_partial_area_suspension_retains_the_same_terrain_contributions(game):
    caster = actor(game)
    zone = GreaseZone(source_entity_uuid=caster.uuid, position=(3, 2),
        affected_positions={(3, 2), (7, 2)})
    zone.activate(parent_event=Event(event_type=EventType.BASE_ACTION, source_entity_uuid=caster.uuid))
    owned = {key: tuple(values) for key, values in zone.modifers_uuids.items()}
    assert get_map().get_tile(3, 2).get_movement_cost(MovementMode.WALKING) == 2
    cast(AntimagicField, caster)
    assert get_map().get_tile(3, 2).get_movement_cost(MovementMode.WALKING) == 1
    assert get_map().get_tile(7, 2).get_movement_cost(MovementMode.WALKING) == 2
    assert zone.applied and zone.affected_positions == {(3, 2), (7, 2)}
    assert {key: tuple(values) for key, values in zone.modifers_uuids.items()} == owned
    caster.remove_condition('Concentrating')
    assert get_map().get_tile(3, 2).get_movement_cost(MovementMode.WALKING) == 2
    assert {key: tuple(values) for key, values in zone.modifers_uuids.items()} == owned


def test_feast_exempt_weaker_source_wins_without_reapplication_or_healing(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    high = HeroesFeastSource(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        feast_uuid=uuid4(), hp_bonus=10)
    low = HeroesFeastSource(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        feast_uuid=uuid4(), hp_bonus=4, antimagic_exception=AntimagicException.DEITY)
    target.add_condition(high)
    target.add_condition(low)
    public = target.active_conditions["Heroes' Feast"]
    before = target.get_normal_hp()
    maximum = target.get_max_hp()
    cast(AntimagicField, caster)
    assert target.active_conditions["Heroes' Feast"] is public
    assert target.get_max_hp() == maximum - 6
    assert target.get_normal_hp() == min(before, maximum - 6)
    before = target.get_normal_hp()
    caster.remove_condition('Concentrating')
    assert target.get_max_hp() == maximum and target.get_normal_hp() == before


def test_teleport_into_field_is_rejected_without_moving(game):
    field_caster = actor(game)
    traveler = actor(game, 'Traveler', (8, 2))
    cast(AntimagicField, field_caster)
    result = MistyStep(source_entity_uuid=traveler.uuid, end_position=(3, 2), alt_skip_slot=True).apply()
    assert result is not None and result.canceled
    assert traveler.position == (8, 2)


def test_magic_weapon_keeps_physical_damage_and_identity_inside_field(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    weapon = build_authored_item('weapon.circus.longsword_plus_one', source_entity_uuid=target.uuid)
    target.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    assert weapon.attack_bonus.score == 1 and weapon.damage_bonus.score == 1
    attack_id = weapon.attack_bonus.get_base_modifier().uuid
    cast(AntimagicField, caster)
    assert target.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is weapon
    assert weapon.attack_bonus.score == 0 and weapon.damage_bonus.score == 0
    assert not weapon.attack_is_magical(target.uuid)
    assert weapon.get_base_damage(target.equipment, target.ability_scores).damage_dice == 8
    caster.remove_condition('Concentrating')
    assert weapon.attack_bonus.score == 1 and weapon.damage_bonus.score == 1
    assert weapon.attack_bonus.get_base_modifier().uuid == attack_id


@pytest.mark.parametrize('expire', [False, True])
def test_summon_is_absent_with_same_identity_and_clock_then_returns_or_expires(battle, expire):
    game, encounter, system, summoner, field_caster = battle
    member = cast_one(battle)
    summoned = member.entity
    Entity.update_entity_position(field_caster, (5, 2))
    member.existence.duration.duration = 2
    cast(AntimagicField, field_caster)
    assert Entity.get(summoned.uuid) is summoned
    assert summoned.is_spatially_suspended and not summoned.is_deployed
    assert not summoned.can_take_actions()
    assert get_map().get_entity_position(summoned.uuid) is None
    assert summoned.uuid in encounter.combatants and summoned.uuid in system.memberships
    summoned.on_turn_start(encounter_uuid=encounter.uuid, round_number=10)
    assert member.existence.duration.duration == 1
    if expire:
        summoned.on_turn_start(encounter_uuid=encounter.uuid, round_number=11)
    field_caster.remove_condition('Concentrating')
    if expire:
        assert Entity.get(summoned.uuid) is None
    else:
        assert Entity.get(summoned.uuid) is summoned and summoned.is_deployed
        assert summoned.position == (4, 2)
        assert member.existence.duration.duration == 1


def test_summon_waits_for_its_occupied_anchor_without_displacing_anyone(battle):
    game, encounter, system, summoner, field_caster = battle
    member = cast_one(battle)
    Entity.update_entity_position(field_caster, (5, 2))
    cast(AntimagicField, field_caster)
    Entity.update_entity_position(summoner, (4, 2))
    field_caster.remove_condition('Concentrating')
    assert summoner.position == (4, 2) and member.entity.is_spatially_suspended
    Entity.update_entity_position(summoner, (3, 2))
    assert member.entity.is_deployed and member.entity.position == (4, 2)


@pytest.mark.parametrize('expire', [False, True])
def test_created_guardian_keeps_clock_and_identity_during_absence(game, expire):
    summoner, field_caster = actor(game), actor(game, 'Field', (10, 2))
    cast(GuardianOfFaith, summoner, end_position=(4, 2))
    zone = next(row for row in get_map().get_spatial_conditions() if isinstance(row, GuardianOfFaithZone))
    guardian = BaseBlock.get(zone.anchor_uuid)
    zone.duration.duration = 2
    Entity.update_entity_position(field_caster, (6, 2))
    cast(AntimagicField, field_caster)
    assert BaseBlock.get(guardian.uuid) is guardian
    assert get_map().get_object_placement(guardian.uuid) is None
    assert zone.applied
    assert not zone.progress_spatial_duration()
    assert zone.duration.duration == 1
    if expire:
        assert zone.progress_spatial_duration()
    field_caster.remove_condition('Concentrating')
    if expire:
        assert BaseBlock.get(guardian.uuid) is None and not zone.applied
    else:
        assert BaseBlock.get(guardian.uuid) is guardian
        assert get_map().get_object_placement(guardian.uuid).position == (4, 2)
        assert zone.applied and zone.duration.duration == 1


def test_physical_arrow_crosses_field_without_its_magic_bonuses(game):
    archer, target, field_caster = actor(game, 'Archer', (1, 2)), actor(game, 'Target', (10, 2), 'enemy'), actor(game, 'Field', (5, 3))
    weapon = Weapon(source_entity_uuid=archer.uuid, item_id='test.antimagic.bow', name='Magic bow',
        damage_dice=8, dice_numbers=1, damage_type=DamageType.PIERCING,
        range=Range(type=RangeType.RANGE, normal=80), properties=[WeaponProperty.RANGED], is_magical=True,
        attack_bonus=ModifiableValue.create(source_entity_uuid=archer.uuid, base_value=2),
        damage_bonus=ModifiableValue.create(source_entity_uuid=archer.uuid, base_value=2),
        extra_damage_dices=[6], extra_damage_dices_numbers=[1], extra_damage_type=[DamageType.FIRE],
        extra_damage_bonus=[ModifiableValue.create(source_entity_uuid=archer.uuid, base_value=0)])
    assert archer.loot_item(weapon) and archer.equip_item(weapon.uuid, WeaponSlot.RANGED_MAIN)
    cast(AntimagicField, field_caster)
    archer.action_economy.reset_all_costs()
    before = target.get_hp()
    with fixed_dice_faces(15, 5):
        result = Attack(source_entity_uuid=archer.uuid, target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN).apply()
    assert result is not None and not result.canceled
    assert result.item_magic_suppression_provider_uuids and not result.attack_is_magical
    assert before - target.get_hp() == 5
    assert weapon.attack_bonus.score == 2 and weapon.damage_bonus.score == 2
    assert len(weapon.get_extra_damages()) == 1


def test_new_condition_starts_suppressed_and_mundane_hidden_stays_live(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    hidden = Hidden(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(hidden)
    cast(AntimagicField, caster)
    haste = HasteEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, tags={ConditionTag.MAGICAL})
    target.add_condition(haste)
    assert haste.applied and not haste.contributions_active()
    assert hidden.applied and hidden.contributions_active()
    assert target.action_economy.current_speed() == 30
    caster.remove_condition('Concentrating')
    assert target.action_economy.current_speed() == 60


def test_magic_item_transfer_recomputes_exact_field_ownership(game):
    caster, holder, receiver = actor(game), actor(game, 'Holder', (3, 2)), actor(game, 'Receiver', (8, 2))
    weapon = build_authored_item('weapon.circus.longsword_plus_one', holder.uuid)
    assert holder.loot_item(weapon) and holder.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    cast(AntimagicField, caster)
    assert weapon.attack_bonus.score == 0
    assert holder.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert holder.drop_item(weapon.uuid, (3, 2)) is weapon
    Entity.update_entity_position(receiver, (4, 2))
    assert receiver.loot_item(weapon)
    Entity.update_entity_position(receiver, (8, 2))
    assert weapon.attack_bonus.score == 1 and not weapon.suppression_provider_uuids


def test_two_fields_keep_created_guardian_absent_until_both_end(game):
    summoner, first, second = actor(game), actor(game, 'First', (10, 2)), actor(game, 'Second', (10, 4))
    cast(GuardianOfFaith, summoner, end_position=(4, 2))
    zone = next(row for row in get_map().get_spatial_conditions() if isinstance(row, GuardianOfFaithZone))
    guardian = BaseBlock.get(zone.anchor_uuid)
    Entity.update_entity_position(first, (6, 2))
    cast(AntimagicField, first)
    Entity.update_entity_position(second, (4, 4))
    cast(AntimagicField, second)
    assert len(guardian.suppression_provider_uuids) == 2
    first.remove_condition('Concentrating')
    assert get_map().get_object_placement(guardian.uuid) is None
    second.remove_condition('Concentrating')
    assert get_map().get_object_placement(guardian.uuid) is not None


def test_explicit_artifact_item_and_deity_effect_bypass_the_field(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    weapon = build_authored_item('weapon.circus.longsword_plus_one', target.uuid)
    weapon.antimagic_exception = AntimagicException.ARTIFACT
    assert target.loot_item(weapon) and target.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    haste = HasteEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}, antimagic_exception=AntimagicException.DEITY)
    target.add_condition(haste)
    cast(AntimagicField, caster)
    assert weapon.attack_bonus.score == 1 and weapon.attack_is_magical(target.uuid)
    assert not weapon.suppression_provider_uuids
    assert haste.contributions_active() and target.action_economy.current_speed() == 60


@pytest.mark.parametrize('spell, zone_type, near_open', [(WallOfForce, WallOfForceZone, True),
    (WallOfStone, WallOfStoneZone, False)])
def test_partial_field_opens_only_magic_wall_cells_and_retains_sections(game, spell, zone_type, near_open):
    wall_caster, field_caster = actor(game), actor(game, 'Field', (5, 2))
    cast(spell, wall_caster, end_position=(5, 4), extra_target_positions=[(11, 4)])
    grid = get_map()
    zone = next(row for row in grid.get_spatial_conditions() if isinstance(row, zone_type))
    identities = tuple(zone.sections)
    assert not grid.can_reach_between((5, 3), (5, 5), PhysicalAccess.PROJECTILE, wall_caster.uuid)
    cast(AntimagicField, field_caster)
    assert grid.can_reach_between((5, 3), (5, 5), PhysicalAccess.PROJECTILE, wall_caster.uuid) is near_open
    assert not grid.can_reach_between((10, 3), (10, 5), PhysicalAccess.PROJECTILE, wall_caster.uuid)
    assert tuple(zone.sections) == identities
    field_caster.remove_condition('Concentrating')
    assert not grid.can_reach_between((5, 3), (5, 5), PhysicalAccess.PROJECTILE, wall_caster.uuid)
    assert tuple(zone.sections) == identities


def test_prepared_magic_potion_use_rejects_before_consuming_its_charge(game):
    caster, target = actor(game), actor(game, 'Recipient', (3, 2))
    potion = build_authored_item('consumable.healing_potion', target.uuid)
    assert target.loot_item(potion)
    target.receive_damage(20, DamageType.SLASHING, target.uuid)
    action = potion.get_use_actions(target.uuid)[0]
    instance = action.instantiate() if action.template else action
    cast(AntimagicField, caster)
    before = target.get_hp(), potion.charges
    result = instance.apply()
    assert result is None or result.canceled
    assert (target.get_hp(), potion.charges) == before
    assert BaseBlock.get(potion.uuid) is potion


def test_moving_existing_area_recomputes_suppression_at_its_new_cells(game):
    caster = actor(game)
    zone = GreaseZone(source_entity_uuid=caster.uuid, position=(7, 2), affected_positions={(7, 2)})
    cause = Event(event_type=EventType.BASE_ACTION, source_entity_uuid=caster.uuid)
    zone.activate(parent_event=cause)
    cast(AntimagicField, caster)
    zone.change_footprint({(3, 3), (7, 3)}, parent_event=cause)
    assert get_map().get_tile(3, 3).get_movement_cost(MovementMode.WALKING) == 1
    assert get_map().get_tile(7, 3).get_movement_cost(MovementMode.WALKING) == 2
    caster.remove_condition('Concentrating')
    assert get_map().get_tile(3, 3).get_movement_cost(MovementMode.WALKING) == 2


@pytest.mark.parametrize("destination", [(7, 4), (9, 4)])
def test_antimagic_blocks_magical_transfer_path_and_landing_but_not_its_permission(game, destination):
    field_owner=actor(game,"Field",(7,2))
    caster=actor(game,"Mover",(3,6))
    target=actor(game,"Ally",(4,4))
    cast(AntimagicField,field_owner)
    before=target.get_normal_hp()
    result=Telekinesis(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
        end_position=destination,alt_skip_slot=True).apply()
    assert result is not None
    assert target.position==(4,4)
    assert target.get_normal_hp()==before
    assert caster.get_action_template("Telekinesis: Move") is not None
