"""Placed spell grants keep spell rules while authoring range and selected aim."""

import pytest

from dnd.actions import Move, SpellAction, SpellEvent
from dnd.actions_functional import execute_available_action, execute_use_action, get_available_actions
from dnd.conditions import Invisible
from dnd.content.items.environment_item_builders import (
    build_arcane_machine_gun,
    build_fireball_cannon,
    build_spell_device,
)
from dnd.core.base_actions import AvailableTarget, TargetType
from dnd.core.creature_types import CreatureType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.entity import Entity
from dnd.spells.enchantment import HoldPerson, Sleep
from dnd.spells.conjuration import MistyStep, PoisonSpray
from dnd.spells.ice_knife import IceKnife
from dnd.spells.necromancy import ChillTouch, InflictWounds
from dnd.spells.divination import TrueSeeing
from dnd.spells.transmutation import JumpSpell
from dnd.spells.evocation import Fireball, FireBolt, MagicMissile, ShockingGrasp
from tests.engine.support import deal_damage_to, force_spell_attack_hit, get_hp, set_hp
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster,
    create_target,
    item_action,
    reset_item_arena,
)


def spell_grant[SpellT: SpellAction](caster: Entity, spell_type: type[SpellT], *,
                                   range_feet: int = 60, sector: float | None = 45) -> SpellT:
    return spell_type(source_entity_uuid=caster.uuid, caster_level=5, template=True,
                      cast_origin="source_item", alt_range=range_feet,
                      target_sector_degrees=sector)


def slot_values(caster: Entity) -> tuple[int, ...]:
    return tuple(caster.action_economy.spell_slot_value(level).normalized_score
                 for level in range(1, 5))


def test_default_arcane_device_uses_sleep_pool_at_the_selected_area_and_wakes_on_damage() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    low = create_target((9, 10), name="Low HP")
    outside_sector = create_target((8, 13), name="Outside aiming sector")
    high = create_target((10, 10), name="Above remaining pool")
    undead = create_target((9, 11), name="Undead")
    immune = create_target((9, 9), name="Charm immune")
    actors = (low, outside_sector, high, undead, immune)
    for actor, hp in zip(actors, (5, 10, 20, 1, 1)):
        set_hp(actor, hp)
    undead.creature_type = CreatureType.UNDEAD
    immune.add_condition_immunity("Charmed", immunity_name="Authored immunity")
    device = build_arcane_machine_gun(caster.uuid, charges=2)
    grant = device.use_action_templates[0]
    assert isinstance(grant, Sleep)
    grant.hp_pool_rolled = grant.hp_pool_remaining = 16
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    info = item_action(caster, device.uuid, "Sleep")
    assert info.target_type is TargetType.POSITION_AOE
    assert outside_sector.position not in {row.position for row in info.valid_targets}
    selected = next(row for row in info.valid_targets if row.position == low.position)
    assert {low.uuid, outside_sector.uuid}.issubset(selected.affected_entity_uuids or ())
    hp_before, slots_before = tuple(get_hp(actor) for actor in actors), slot_values(caster)
    cursor = EventQueue.event_cursor()
    result = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    assert result.behavior_id == "spell.sleep" and result.total_damage == 0
    assert result.cast_origin == "source_item" and result.source_item_uuid == device.uuid
    assert result.source_entity_uuid == caster.uuid and result.source_position == caster.position
    assert result.aoe_position == low.position and result.range_ft == 90
    assert result.resolved_area_positions is not None
    assert low.position in result.resolved_area_positions and outside_sector.position in result.resolved_area_positions
    assert (0, 0) not in result.resolved_area_positions
    assert tuple(get_hp(actor) for actor in actors) == hp_before
    assert ["Sleep" in actor.active_conditions for actor in actors] == [True, True, False, False, False]
    assert low.action_economy.action_permission.normalized_score == 0
    assert low.senses.visual_access.normalized_score == 0
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert not any(event.event_type is EventType.DAMAGE_APPLIED for event in events)
    applications = [event for event in events if isinstance(event, SpellEvent)
                    and event.phase is EventPhase.COMPLETION and event.parent_lineage == result.lineage_uuid]
    assert [(event.application_index, event.target_entity_uuid) for event in applications] == [
        (0, low.uuid), (1, outside_sector.uuid)]
    assert len({event.application_id for event in applications}) == 2
    assert device.charges == 1 and caster.action_economy.actions.normalized_score == 0
    assert slot_values(caster) == slots_before
    deal_damage_to(low, 1, source_uuid=caster.uuid)
    assert "Sleep" not in low.active_conditions and "Sleep" in outside_sector.active_conditions
    assert low.action_economy.action_permission.normalized_score == 1
    assert low.senses.visual_access.normalized_score == 1


def test_sleep_device_range_uses_emitter_and_not_operator_position() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    target = create_target((6, 10))
    set_hp(target, 5)
    grant = spell_grant(caster, Sleep, range_feet=5)
    grant.hp_pool_rolled = grant.hp_pool_remaining = 5
    device = build_arcane_machine_gun(caster.uuid, spell_templates=[grant], charges=1)
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    info = item_action(caster, device.uuid, "Sleep")
    selected = next(row for row in info.valid_targets if row.position == target.position)
    assert selected.distance == 5 and caster.senses.get_feet_distance(target.position) == 10
    result = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert "Sleep" in target.active_conditions and get_hp(target) == 5
    assert result.range_ft == 5 and result.source_position == (4, 10)
    assert device.charges == 0


@pytest.mark.parametrize("position, reason", (((5, 14), "firing sector"), ((14, 10), "out of range")))
def test_sleep_device_rejects_invalid_area_without_condition_or_cost(position, reason) -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    target = create_target(position)
    set_hp(target, 5)
    grant = spell_grant(caster, Sleep, range_feet=20)
    grant.hp_pool_rolled = grant.hp_pool_remaining = 5
    device = build_arcane_machine_gun(caster.uuid, spell_templates=[grant], charges=1)
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    slots_before = slot_values(caster)
    template = device.get_use_actions(caster.uuid)[0]
    result = execute_use_action(caster, device.uuid, template.get_discovery_template_name(),
                                AvailableTarget(index=0, position=position))
    assert result is not None and result.canceled and reason in (result.status_message or "")
    assert "Sleep" not in target.active_conditions and get_hp(target) == 5
    assert device.charges == 1 and caster.action_economy.actions.normalized_score == 1
    assert slot_values(caster) == slots_before


@pytest.mark.parametrize("spell_type", (Fireball, MagicMissile, FireBolt, ChillTouch, IceKnife,
                                        PoisonSpray, InflictWounds))
def test_device_range_and_recorded_origin_are_independent_of_operator(spell_type: type[SpellAction]) -> None:
    reset_item_arena()
    caster = create_caster((2, 5))
    target = create_target((4, 5))
    grant = spell_grant(caster, spell_type, range_feet=5)
    device = build_spell_device(item_id="environment.fireball_cannon", name="Test Cannon",
                               spell_templates=[grant], charges=2)
    device.place_on_grid((3, 5))
    Entity.update_all_entities_senses()
    force_spell_attack_hit(caster)
    assert grant.name is not None
    info = item_action(caster, device.uuid, grant.name)
    row = next(row for row in info.valid_targets
               if (row.position == target.position if info.target_type is TargetType.POSITION_AOE
                   else row.target_uuid == target.uuid))
    assert caster.senses.get_feet_distance(target.position) == 10
    assert row.distance == 5
    hp_before, slots_before = get_hp(target), slot_values(caster)
    with fixed_dice_faces(*([2] * 100)):
        result = execute_use_action(caster, device.uuid, info.template_name, row)
    assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
    assert isinstance(result, SpellEvent)
    assert result.cast_origin == "source_item"
    assert result.source_position == (2, 5)
    assert result.source_entity_uuid == caster.uuid
    assert result.source_item_uuid == device.uuid
    assert result.range_ft == 5
    assert get_hp(target) < hp_before
    assert caster.action_economy.actions.normalized_score == 0
    assert slot_values(caster) == slots_before
    assert device.charges == 1


@pytest.mark.parametrize("operator_position, target_position, reason", (
    ((1, 10), (8, 10), "stand beside"),
    ((5, 10), (8, 10), "stand beside"),
    ((6, 10), (8, 10), "outside the device firing sector"),
    ((4, 10), (9, 12), "outside the device firing sector"),
    ((4, 10), (10, 10), "out of range"),
))
def test_direct_device_commands_recheck_position_sector_and_range_without_spending(
    operator_position: tuple[int, int], target_position: tuple[int, int], reason: str,
) -> None:
    reset_item_arena()
    caster = create_caster(operator_position)
    target = create_target(target_position)
    cannon = build_fireball_cannon(charges=2, range_feet=20)
    cannon.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    hp_before, slots_before = get_hp(target), slot_values(caster)
    action_name = cannon.get_use_actions(caster.uuid)[0].get_discovery_template_name()
    result = execute_use_action(caster, cannon.uuid, action_name,
                                AvailableTarget(index=0, position=target_position))
    assert result is not None and result.canceled
    assert result.status_message is not None
    assert reason in result.status_message
    assert cannon.charges == 2
    assert caster.action_economy.actions.normalized_score == 1
    assert slot_values(caster) == slots_before
    assert get_hp(target) == hp_before


def test_operator_walk_changes_the_sector_and_rejects_the_old_selection() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    east = create_target((8, 10))
    west = create_target((2, 10))
    device = build_arcane_machine_gun(caster.uuid, charges=2,
                                     spell_templates=[spell_grant(caster, MagicMissile)])
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    before = item_action(caster, device.uuid, "Magic Missile")
    assert {row.target_uuid for row in before.valid_targets} == {east.uuid}
    old_selection = before.valid_targets[0]
    movement_before = caster.action_economy.movement.normalized_score
    moved = Move(source_entity_uuid=caster.uuid, end_position=(6, 10)).apply()
    assert moved is not None and not moved.canceled
    assert caster.position == (6, 10)
    assert caster.action_economy.movement.normalized_score < movement_before
    after = item_action(caster, device.uuid, "Magic Missile")
    assert {row.target_uuid for row in after.valid_targets} == {west.uuid}
    rejected = execute_use_action(caster, device.uuid, before.template_name, old_selection)
    assert rejected is not None and rejected.canceled
    assert device.charges == 2 and caster.action_economy.actions.normalized_score == 1
    with fixed_dice_faces(2, 2, 2):
        accepted = execute_use_action(caster, device.uuid, after.template_name, after.valid_targets[0])
    assert accepted is not None and not accepted.canceled
    assert device.charges == 1


@pytest.mark.parametrize("sector", (None, 45))
def test_magic_missile_validates_every_selected_recipient_without_rewriting_homing(sector: float | None) -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    east = create_target((9, 10))
    north = create_target((5, 14))
    device = build_arcane_machine_gun(caster.uuid, charges=2,
                                     spell_templates=[spell_grant(caster, MagicMissile, sector=sector)])
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    info = item_action(caster, device.uuid, "Magic Missile")
    assert {row.target_uuid for row in info.valid_targets} == (
        {east.uuid, north.uuid} if sector is None else {east.uuid})
    selected = AvailableTarget(index=0, target_uuid=east.uuid,
                               extra_target_uuids=[north.uuid, east.uuid])
    hp_before = (get_hp(east), get_hp(north))
    with fixed_dice_faces(2, 2, 2):
        result = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert result is not None
    if sector is not None:
        assert result.canceled
        assert (get_hp(east), get_hp(north)) == hp_before
        assert device.charges == 2 and caster.action_economy.actions.normalized_score == 1
        return
    assert not result.canceled
    assert (get_hp(east), get_hp(north)) == (hp_before[0] - 6, hp_before[1] - 3)
    applications = [event for _, event in EventQueue.iter_events_since(0)
                    if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION
                    and event.parent_lineage == result.lineage_uuid and event.application_index is not None]
    assert [(event.application_index, event.target_entity_uuid) for event in applications] == [
        (0, east.uuid), (1, north.uuid), (2, east.uuid)]
    assert all(event.cast_origin == "source_item" and event.source_item_uuid == device.uuid
               and event.source_entity_uuid == caster.uuid for event in applications)


def test_fireball_sector_limits_aim_without_clipping_the_explosion() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    inside_aim = create_target((9, 11))
    outside_aim = create_target((8, 13))
    cannon = build_fireball_cannon()
    cannon.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    info = item_action(caster, cannon.uuid, "Fireball")
    assert outside_aim.position not in {row.position for row in info.valid_targets}
    selected = next(row for row in info.valid_targets if row.position == inside_aim.position)
    assert selected.affected_entity_uuids is not None
    assert outside_aim.uuid in selected.affected_entity_uuids
    hp_before = (get_hp(inside_aim), get_hp(outside_aim))
    with fixed_dice_faces(*([2] * 100)):
        result = execute_use_action(caster, cannon.uuid, info.template_name, selected)
    assert result is not None and not result.canceled
    assert isinstance(result, SpellEvent)
    assert result.aoe_position == inside_aim.position
    assert result.resolved_area_positions is not None
    assert outside_aim.position in result.resolved_area_positions
    assert get_hp(inside_aim) < hp_before[0] and get_hp(outside_aim) < hp_before[1]


def test_one_device_body_can_supply_independently_configured_spells() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    target = create_target((10, 10))
    cannon = build_fireball_cannon(spell_templates=[
        spell_grant(caster, Fireball, range_feet=225),
        spell_grant(caster, MagicMissile, range_feet=60, sector=None),
    ])
    cannon.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    grants = cannon.get_use_actions(caster.uuid)
    grant_facts = []
    for grant in grants:
        assert isinstance(grant, SpellAction)
        grant_facts.append((grant.name, grant.cast_at_level, grant.get_range().normal))
    assert grant_facts == [
        ("Fireball", 3, 225), ("Magic Missile", 1, 60)]
    rows = [row for row in get_available_actions(caster).all_actions if row.source_item_uuid == cannon.uuid]
    assert len(rows) == 2
    for name in ("Magic Missile", "Fireball"):
        caster.action_economy.reset_all_costs()
        info = item_action(caster, cannon.uuid, name)
        selected = next(row for row in info.valid_targets
                        if (row.position == target.position if info.target_type is TargetType.POSITION_AOE
                            else row.target_uuid == target.uuid))
        with fixed_dice_faces(*([2] * 100)):
            result = execute_use_action(caster, cannon.uuid, info.template_name, selected)
        assert result is not None and not result.canceled
        assert isinstance(result, SpellEvent)
        assert result.name == name
        assert result.source_item_uuid == cannon.uuid
        assert result.source_item_presentation is not None
        assert result.source_item_presentation.item_id == "environment.fireball_cannon"
    assert cannon.charges == 1


def test_two_devices_sharing_a_spell_keep_their_own_discovery_distances() -> None:
    reset_item_arena()
    caster = create_caster((5, 10))
    create_target((10, 10))
    shared_grant = spell_grant(caster, Fireball, range_feet=225, sector=None)
    west = build_fireball_cannon(spell_templates=[shared_grant])
    east = build_fireball_cannon(spell_templates=[shared_grant])
    west.place_on_grid((4, 10))
    east.place_on_grid((6, 10))
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    rows = {info.source_item_uuid: info for info in available.all_actions
            if info.source_item_uuid in {west.uuid, east.uuid}}
    assert set(rows) == {west.uuid, east.uuid}
    assert {row.position for row in rows[west.uuid].valid_targets} == {
        row.position for row in rows[east.uuid].valid_targets}
    distances = {identity: next(row.distance for row in info.valid_targets if row.position == (10, 10))
                 for identity, info in rows.items()}
    assert distances == {west.uuid: 30, east.uuid: 20}


@pytest.mark.parametrize("operator_position, target_position, accepted", (
    ((4, 10), (9, 14), True),
    ((4, 10), (9, 15), False),
    ((6, 10), (1, 14), True),
    ((6, 10), (1, 15), False),
    ((4, 9), (10, 10), True),
    ((4, 9), (10, 9), False),
))
def test_authored_sector_boundary_matches_discovery_and_execution(
    operator_position: tuple[int, int], target_position: tuple[int, int], accepted: bool,
) -> None:
    reset_item_arena()
    caster = create_caster(operator_position)
    target = create_target(target_position)
    gun = build_arcane_machine_gun(caster.uuid, charges=1,
                                  spell_templates=[spell_grant(caster, MagicMissile, sector=90)])
    gun.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    exposed = any(row.target_uuid == target.uuid for info in available.all_actions
                  if info.source_item_uuid == gun.uuid for row in info.valid_targets)
    assert exposed is accepted
    action_name = gun.get_use_actions(caster.uuid)[0].get_discovery_template_name()
    hp_before = get_hp(target)
    with fixed_dice_faces(2, 2, 2):
        result = execute_use_action(caster, gun.uuid, action_name,
                                    AvailableTarget(index=0, target_uuid=target.uuid))
    assert result is not None and result.canceled == (not accepted)
    assert get_hp(target) == hp_before - (9 if accepted else 0)
    assert gun.charges == (0 if accepted else 1)
    assert caster.action_economy.actions.normalized_score == (0 if accepted else 1)


@pytest.mark.parametrize("spell_type, condition", (
    (HoldPerson, "Hold Person"), (TrueSeeing, "True Seeing"), (JumpSpell, "Jump"),
    (PoisonSpray, None), (InflictWounds, None), (ShockingGrasp, None),
))
@pytest.mark.parametrize("range_feet", (5, 20))
def test_device_primary_range_overrides_reach_real_spell_effects(
    spell_type: type[SpellAction], condition: str | None, range_feet: int,
) -> None:
    reset_item_arena()
    caster = create_caster((2, 5))
    target = create_target((3 + range_feet // 5, 5),
                           faction="monsters" if condition == "Hold Person" or condition is None else "heroes")
    grant = spell_grant(caster, spell_type, range_feet=range_feet)
    device = build_spell_device(item_id="environment.fireball_cannon", name="Range test device",
        spell_templates=[grant], charges=1)
    device.place_on_grid((3, 5))
    Entity.update_all_entities_senses()
    force_spell_attack_hit(caster)
    info = item_action(caster, device.uuid, grant.name)
    selected = next(row for row in info.valid_targets if row.target_uuid == target.uuid)
    assert selected.distance == range_feet
    hp_before, slots_before = get_hp(target), slot_values(caster)
    with fixed_dice_faces(*([2] * 50)):
        event = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(event, SpellEvent) and not event.canceled
    assert event.source_item_uuid == device.uuid and event.source_entity_uuid == caster.uuid
    assert event.range_ft == range_feet
    if condition is not None:
        assert condition in target.active_conditions
        assert get_hp(target) == hp_before
    else:
        assert get_hp(target) < hp_before
    assert device.charges == 0 and slot_values(caster) == slots_before
    assert caster.action_economy.actions.normalized_score == 0
    if spell_type is HoldPerson:
        assert "Concentrating" in device.active_conditions
        assert "Concentrating" not in caster.active_conditions


@pytest.mark.parametrize("spell_type", (HoldPerson, ChillTouch, IceKnife, PoisonSpray, InflictWounds))
def test_mage_primary_range_and_device_origin_do_not_change_each_other(spell_type: type[SpellAction]) -> None:
    reset_item_arena()
    caster = create_caster((2, 5))
    near = create_target((3, 5), name="Within mage range")
    far = create_target((4, 5), name="Outside mage range")
    template = spell_type(source_entity_uuid=caster.uuid, caster_level=5, alt_range=5, template=True)
    caster.register_action(template)
    Entity.update_all_entities_senses()
    force_spell_attack_hit(caster)
    available = get_available_actions(caster)
    info = next(row for row in available.all_actions
                if (row.base_template_name or row.template_name) == template.name
                and (row.cast_at_level or 0) == template.spell_level)
    assert {row.target_uuid for row in info.valid_targets} == {near.uuid}
    action_before, slots_before = caster.action_economy.actions.normalized_score, slot_values(caster)
    rejected = execute_available_action(caster, info, AvailableTarget(index=0, target_uuid=far.uuid))
    assert rejected is not None and rejected.canceled
    assert caster.action_economy.actions.normalized_score == action_before
    assert slot_values(caster) == slots_before
    with fixed_dice_faces(*([2] * 50)):
        accepted = execute_available_action(caster, info, info.valid_targets[0])
    assert isinstance(accepted, SpellEvent) and not accepted.canceled
    assert accepted.cast_origin == "actor" and accepted.source_item_uuid is None
    assert accepted.source_position == caster.position
    assert caster.action_economy.actions.normalized_score == 0


def test_device_does_not_make_an_unseen_target_visible_to_its_operator() -> None:
    reset_item_arena()
    caster = create_caster((2, 5))
    target = create_target((4, 5))
    target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    device = build_spell_device(item_id="environment.fireball_cannon", name="Range test device",
        spell_templates=[spell_grant(caster, HoldPerson, range_feet=5)], charges=1)
    device.place_on_grid((3, 5))
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    assert not any(row.target_uuid == target.uuid for info in available.all_actions
                   if info.source_item_uuid == device.uuid for row in info.valid_targets)
    grant = device.get_use_actions(caster.uuid)[0]
    slots_before = slot_values(caster)
    event = execute_use_action(caster, device.uuid, grant.get_discovery_template_name(),
                               AvailableTarget(index=0, target_uuid=target.uuid))
    assert event is not None and event.canceled
    assert "Hold Person" not in target.active_conditions
    assert device.charges == 1 and slot_values(caster) == slots_before
    assert caster.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize("range_feet, destination", ((5, (4, 5)), (40, (11, 5))))
def test_misty_step_device_uses_authored_destination_range(range_feet, destination) -> None:
    reset_item_arena()
    caster = create_caster((2, 5))
    device = build_spell_device(item_id="environment.fireball_cannon", name="Teleport device",
        spell_templates=[spell_grant(caster, MistyStep, range_feet=range_feet)], charges=1)
    device.place_on_grid((3, 5))
    Entity.update_all_entities_senses()
    info = item_action(caster, device.uuid, "Misty Step")
    selected = next(row for row in info.valid_targets if row.position == destination)
    assert selected.distance == range_feet
    slots_before = slot_values(caster)
    event = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(event, SpellEvent) and not event.canceled
    assert caster.position == destination and event.source_position == (2, 5)
    assert event.source_item_uuid == device.uuid and event.source_entity_uuid == caster.uuid
    assert device.charges == 0 and slot_values(caster) == slots_before
