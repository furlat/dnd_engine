"""Native force boundaries, shell travel, summon damage and rejected follow-ups."""

import pytest

from dnd.actions import (
    AllyHelp,
    Attack,
    Dodge,
    ShakeAwake,
    Shove,
    commit_forced_movement,
)
from dnd.actions_functional import execute_use_action
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    EventHandler,
    EventPhase,
    EventType,
    ForcedMovementEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from dnd.items.consumables import build_healing_potion
from dnd.spells.abjuration import (
    AntilifeShell,
    AntilifeShellZone,
    BreakEnchantment,
    DispelEvilAndGood,
    GlyphSleepEffect,
)
from dnd.spells.conjuration import MistyStep
from dnd.spells.enchantment import CharmMonster
from dnd.spells.evocation import ResilientSphere, ScorchingRay, VitriolicSphere
from dnd.spells.summoning import ConjureElemental
from tests.engine.test_bg3_rank_one_two_spells import game as game
from tests.engine.test_high_level_spell_controls import cast, high_actor
from tests.engine.test_high_level_spell_summons import summon
from tests.engine.test_summoning_lifecycle import battle as battle
from tests.manual.spell_regression_support import force_save_result
from dnd.core.values import Channel, Kind, add_modifier


@pytest.mark.parametrize("kind", [Shove, AllyHelp, ShakeAwake])
def test_sphere_rejects_external_contact_actions(game, kind):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (4, 2))
    helper = high_actor(game, "Helper", (3, 2))
    enemy = high_actor(game, "Enemy", (5, 2), "foes")
    sleep = GlyphSleepEffect(
        source_entity_uuid=enemy.uuid, target_entity_uuid=target.uuid
    )
    if kind is not Shove:
        target.add_condition(sleep)
    cast(ResilientSphere, caster, target)
    Entity.update_all_entities_senses()
    old = target.position
    result = kind(
        source_entity_uuid=helper.uuid, target_entity_uuid=target.uuid
    ).apply()
    accepted = result is not None and not result.canceled
    position = target.position
    sleep_active = sleep.applied
    assert not accepted, "External contact must be rejected by Sphere"
    assert position == old
    if kind is not Shove:
        assert sleep_active, "External assistance cannot cross Sphere"


def test_sphere_blocks_direct_native_forced_movement(game):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (4, 2))
    helper = high_actor(game, "Helper", (3, 2))
    cast(ResilientSphere, caster, target)
    movement = ForcedMovementEvent(
        source_entity_uuid=helper.uuid,
        target_entity_uuid=target.uuid,
        start_position=target.position,
        end_position=(5, 2),
        direction=(1, 0),
        intended_distance=5,
        actual_distance=5,
        cause="review_external_push",
    )
    movement = movement.phase_to(EventPhase.EXECUTION)
    movement = movement.phase_to(EventPhase.EFFECT)
    movement = commit_forced_movement(target, movement, parent_event=movement)
    position = target.position
    assert position == (4, 2)


def test_sphere_self_dodge_and_nonspell_healing_remain_legal(game):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (4, 2))
    target.receive_damage(10, DamageType.FORCE, caster.uuid)
    cast(ResilientSphere, caster, target)
    result = Dodge(source_entity_uuid=target.uuid).apply()
    accepted = result is not None and not result.canceled
    healed = target.receive_healing(5, target.uuid)
    assert accepted
    assert healed == 5




def test_tenacity_critical_miss_still_deals_four(battle):
    _, _, system, caster, target = battle
    Entity.update_entity_position(target, (5, 2))
    Entity.update_all_entities_senses()
    creation = ConjureElemental(
        source_entity_uuid=caster.uuid,
        form_id="air_myrmidon",
        cast_at_level=6,
        end_position=(4, 2),
    ).apply()
    created = creation is not None and not creation.canceled
    assert created
    actor = next(iter(system.memberships.values())).entity
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(*([1] * 12)):
        result = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    outcome = result.attack_outcome if result is not None else None
    damage = hp - target.get_hp()
    assert outcome is AttackOutcome.CRIT_MISS, str(outcome)
    assert damage == 4, f"Critical miss Tenacity should deal 4; dealt {damage}"


def test_shell_teleport_does_not_sweep_intermediate_creature(game):
    caster = high_actor(game)
    high_actor(game, "Middle", (5, 2), "foes")
    cast(AntilifeShell, caster)
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = MistyStep(source_entity_uuid=caster.uuid, end_position=(8, 2)).apply()
    position = caster.position
    retained = "Concentrating" in caster.active_conditions
    accepted = result is not None and not result.canceled
    assert accepted
    assert position == (8, 2)
    assert retained, "Teleport does not sweep the shell through intermediate cells"


def test_shell_recomputes_round_footprint_after_leaving_map_edge(game):
    caster = high_actor(game, position=(1, 2))
    cast(AntilifeShell, caster)
    Entity.update_entity_position(caster, (2, 2))
    zones = [
        zone
        for zone in get_map().get_spatial_conditions()
        if isinstance(zone, AntilifeShellZone)
    ]
    assert len(zones) == 1
    cells = set(zones[0].affected_positions)
    assert (0, 2) in cells, "The left fringe remains within ten feet of the new anchor"


def test_shell_initial_edge_occupant_remains_enclosed_after_move(game):
    caster = high_actor(game, position=(1, 2))
    high_actor(game, "Enclosed", (0, 2))
    cast(AntilifeShell, caster)
    Entity.update_entity_position(caster, (2, 2))
    retained = "Concentrating" in caster.active_conditions
    assert retained, (
        "A creature inside both old and new shells did not cross the boundary"
    )


def test_break_enchantment_late_veto_preserves_charm_and_ward(game):
    caster = high_actor(game, position=(3, 2))
    target = high_actor(game, "Charmed", (4, 2))
    fey = high_actor(game, "Fey", (5, 2), "foes", creature_type=CreatureType.FEY)
    force_save_result(target, "wisdom", succeeds=False)
    cast(CharmMonster, fey, target)
    cast(DispelEvilAndGood, caster)
    charm = next(
        condition
        for condition in target.active_conditions_by_uuid.values()
        if condition.get_display_name() == "Charm Monster"
    )
    action = next(
        action
        for action in caster.registered_actions
        if isinstance(action, BreakEnchantment)
    )
    caster.action_economy.reset_all_costs()

    def veto(event, owner_uuid):
        if event.behavior_id == "action.spell.dispel_evil_and_good.break_enchantment":
            return event.cancel(status_message="Review late veto")
        return None

    caster.add_event_handler(
        EventHandler(
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT)
            ],
            event_processor=veto,
        )
    )
    result = action.instantiate(target_entity_uuid=target.uuid).apply()
    canceled = result is not None and result.canceled
    charm_retained = charm.applied
    ward_retained = any(
        condition.get_display_name() == "Dispel Evil and Good"
        for condition in caster.active_conditions_by_uuid.values()
    )
    assert canceled
    assert charm_retained and ward_retained, (
        "Rejected Break Enchantment cannot commit either removal"
    )


BASIC_HITS = (
    ("air_elemental", 10, 18),
    ("earth_elemental", 9, 13),
    ("fire_elemental", 8, 16),
    ("water_elemental", 12, 20),
    ("air_myrmidon", 11, 15),
    ("earth_myrmidon", 15, 21),
    ("fire_myrmidon", 11, 15),
    ("water_myrmidon", 11, 15),
    ("deva", 14, 24),
    ("djinni", 12, 18),
    ("draconic_spirit", 11, 13),
)


@pytest.mark.parametrize("critical", [False, True])
@pytest.mark.parametrize("body,normal_damage,critical_damage", BASIC_HITS)
def test_all_bound_body_basic_attack_numeric_damage(
    battle, body, normal_damage, critical_damage, critical
):
    _, _, _, _, target = battle
    Entity.update_entity_position(target, (5, 2))
    actor = summon(battle, body).entity
    Entity.update_all_entities_senses()
    template = next(
        action for action in actor.registered_actions if type(action) is Attack
    )
    hp = target.get_hp()
    with fixed_dice_faces(20 if critical else 15, *([2] * 40)):
        result = template.instantiate(target_entity_uuid=target.uuid).apply()
    outcome = result.attack_outcome if result is not None else None
    damage = hp - target.get_hp()
    expected = critical_damage if critical else normal_damage
    assert outcome is (AttackOutcome.CRIT if critical else AttackOutcome.HIT), str(
        outcome
    )
    assert damage == expected, f"{body}: expected {expected}; dealt {damage}"
    remaining = actor.action_economy.actions.normalized_score
    assert remaining == 0


@pytest.mark.parametrize("critical", [False, True])
def test_cambion_actual_srd_rays_numeric_damage(battle, critical):
    _, _, _, _, target = battle
    Entity.update_entity_position(target, (8, 2))
    actor = summon(battle, "cambion").entity
    Entity.update_all_entities_senses()
    template = next(
        action
        for action in actor.registered_actions
        if isinstance(action, ScorchingRay)
    )
    hp = target.get_hp()
    sequence = [20, 2, 2, 2, 2] if critical else [15, 2, 2]
    with fixed_dice_faces(*(sequence * 3)):
        result = template.instantiate(target_entity_uuid=target.uuid).apply()
    accepted = result is not None and not result.canceled
    damage = hp - target.get_hp()
    expected = 24 if critical else 12
    assert accepted
    assert damage == expected, f"Expected {expected}; dealt {damage}"


@pytest.mark.parametrize("enclose_emitter", [False, True])
def test_sphere_blocks_existing_residue_but_not_deadline_or_owner_cleanup(
    game, enclose_emitter
):
    sphere_caster = high_actor(game, position=(2, 2))
    acid_caster = high_actor(
        game, "Acid caster", (3, 2) if enclose_emitter else (10, 2), "foes"
    )
    target = high_actor(game, "Residue target", (8, 2) if enclose_emitter else (4, 2))
    force_save_result(target, "dexterity", succeeds=False)
    with fixed_dice_faces(*([2] * 200)):
        cast(VitriolicSphere, acid_caster, end_position=target.position)
    enclosed = acid_caster if enclose_emitter else target
    force_save_result(enclosed, "dexterity", succeeds=False)
    cast(ResilientSphere, sphere_caster, enclosed)
    hp = target.get_hp()
    with fixed_dice_faces(*([2] * 100)):
        target.on_turn_end()
    actual_hp = target.get_hp()
    residue_retained = any(
        condition.get_display_name() == "Vitriolic Residue"
        for condition in target.active_conditions_by_uuid.values()
    )
    sphere_caster.remove_condition("Concentrating")
    sphere_retained = any(
        condition.get_display_name() == "Resilient Sphere"
        for condition in enclosed.active_conditions_by_uuid.values()
    )
    assert actual_hp == hp
    assert not residue_retained
    assert not sphere_retained


def test_sphere_allows_held_self_consumable_through_native_item_action(game):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (4, 2))
    target.receive_damage(10, DamageType.FORCE, caster.uuid)
    potion = build_healing_potion(target.uuid, heal_amount=5)
    loaded = target.loot_item(potion)
    assert loaded
    cast(ResilientSphere, caster, target)
    hp = target.get_hp()
    result = execute_use_action(target, potion.uuid, "Drink Potion")
    accepted = result is not None and not result.canceled
    restored = target.get_hp() - hp
    remaining = target.action_economy.bonus_actions.normalized_score
    assert accepted
    assert restored == 5
    assert remaining == 0


@pytest.mark.parametrize("strength,expected", [(14, 2), (8, 1)])
def test_tenacity_uses_current_strength_modifier_with_minimum_one(
    battle, strength, expected
):
    _, _, _, _, target = battle
    Entity.update_entity_position(target, (5, 2))
    actor = summon(battle, "air_myrmidon").entity
    add_modifier(actor.ability_scores.strength.ability_score, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
            name="Changed Strength", value=strength - 18, source_entity_uuid=actor.uuid
        ))
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(*([1] * 12)):
        Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    damage = hp - target.get_hp()
    assert damage == expected, f"STR {strength}: expected {expected}; dealt {damage}"


def test_tenacity_later_effect_veto_cannot_deal_miss_damage(battle):
    _, _, _, _, target = battle
    Entity.update_entity_position(target, (5, 2))
    actor = summon(battle, "air_myrmidon").entity

    def veto(event, owner_uuid):
        if event.attack_outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS):
            return event.cancel(status_message="Review later miss veto")
        return None

    actor.add_event_handler(
        EventHandler(
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT)
            ],
            event_processor=veto,
        )
    )
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(*([1] * 12)):
        result = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    canceled = result is not None and result.canceled
    damage = hp - target.get_hp()
    assert canceled
    assert damage == 0, f"Canceled attack must not apply Tenacity; dealt {damage}"
