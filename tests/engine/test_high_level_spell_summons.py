"""Approved spell bodies born through the real native summon owner."""

import pytest

from dnd.actions import Attack, Move
from dnd.actions_functional import get_available_actions
from dnd.core.base_actions import ActionEvent
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.condition_types import DurationType
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from dnd.monsters.high_level_spell_summons import BODIES
from dnd.monsters.spell_summon_actions import (
    Burning,
    CinderousSwipe,
    ConcussiveSmash,
    DragonBreath,
    DrainingKiss,
    ElectrifiedFlail,
    ElementalWarp,
    ExplosiveIcicle,
    GroundedThunder,
    GushingAir,
    HealingVapours,
    HiemalStrike,
    Immolation,
    MuckToMetal,
    MyrmidonBurrow,
    MyrmidonCinderousSwipe,
    PrimordialGales,
    RagingVortex,
    RagingVortexZone,
    ScorchingStrike,
    SeismicStrike,
    SludgySling,
    SmoulderingTouch,
    SoilCloggedSlam,
    SweetplumGales,
    SweetplumGalesZone,
    WaterSlam,
    WintersBreath,
)
from dnd.monsters.traits import MultiattackAction, NaturalAttack
from dnd.spells.enchantment import CharmPerson
from dnd.spells.illusion import Invisibility
from dnd.spells.necromancy import Revivify
from dnd.spells.summoning import ConjureElemental, PlanarAlly, SummonDragon
from dnd.spells.transmutation import MagicWeapon
from tests.engine.test_bg3_spell_hit_riders import equip
from tests.engine.test_high_level_spell_controls import high_actor
from tests.engine.test_summoning_autonomous_turns import autonomous_attack, autonomous_battle
from tests.engine.test_summoning_lifecycle import battle
from tests.manual.spell_regression_support import force_save_result
from dnd.core.values import Channel, Kind, add_modifier


def summon(battle, key, *, slot=None, position=(4, 2), form_id=None, **values):
    _, _, system, caster, _ = battle
    spell = (
        SummonDragon
        if key == "draconic_spirit"
        else PlanarAlly
        if key in ("deva", "djinni", "cambion")
        else ConjureElemental
    )
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell(
        source_entity_uuid=caster.uuid,
        form_id=form_id or ("red" if key == "draconic_spirit" else key),
        cast_at_level=slot
        or (5 if key.endswith("elemental") or key == "draconic_spirit" else 6),
        end_position=position,
        **values,
    ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No result"
    )
    return next(
        member
        for member in system.memberships.values()
        if member.entity.position == position
    )


@pytest.mark.parametrize("body", BODIES, ids=lambda body: body.key)
def test_body_native_birth_stats_type_defenses_and_loadout(battle, body):
    game, encounter, system, caster, enemy = battle
    member = summon(battle, body.key)
    actor = member.entity
    assert (
        actor.get_max_hp(),
        actor.ac_bonus().normalized_score,
        actor.size,
        actor.creature_type,
    ) == (body.hp, body.ac, body.size, body.kind)
    assert (
        actor.uuid in encounter.initiative_order
        and game.get_entity(actor.uuid) is actor
    )
    assert actor.health.nonmagical_attack_resistances == (
        {DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING}
        if body.nonmagical_bps
        else frozenset()
    )
    assert len(actor.registered_actions) >= 5
    assert caster.action_economy.actions.normalized_score == 0
    assert member.existence.duration.duration_type is (
        DurationType.ROUNDS
        if body.key == "draconic_spirit"
        else DurationType.UNTIL_LONG_REST
    )
    if body.key != "draconic_spirit":
        assert "Concentrating" not in caster.active_conditions


@pytest.mark.parametrize(
    "slot,hp,ac,rends",
    [(5, 50, 19, 2), (6, 60, 20, 3), (7, 70, 21, 3), (8, 80, 22, 4), (9, 90, 23, 4)],
)
def test_dragon_native_rends_then_one_free_breath_and_exact_cleanup(
    battle, slot, hp, ac, rends
):
    game, _, _, caster, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    member = summon(
        battle,
        "draconic_spirit",
        slot=slot,
        form_id="white",
    )
    dragon = member.entity
    assert (dragon.get_max_hp(), dragon.ac_bonus().normalized_score) == (hp, ac)
    assert caster.health.preview_damage(20, DamageType.COLD).applied_damage == 10
    assert caster.health.preview_damage(20, DamageType.POISON).applied_damage == 20
    Entity.update_all_entities_senses()
    multi = next(
        action
        for action in dragon.registered_actions
        if isinstance(action, MultiattackAction)
    )
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([15, 2] * 10)):
        result = multi.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No result"
    )
    attacks = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.ATTACK
        and event.phase is EventPhase.COMPLETION
        and event.source_entity_uuid == dragon.uuid
    ]
    assert len(attacks) == rends
    free = [
        action
        for action in dragon.registered_actions
        if isinstance(action, DragonBreath) and action.allowance_uuid is not None
    ]
    assert len(free) == 1 and dragon.action_economy.actions.normalized_score == 0
    result = free[0].instantiate(end_position=enemy.position).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No result"
    )
    assert not any(
        isinstance(action, DragonBreath) and action.allowance_uuid is not None
        for action in dragon.registered_actions
    )
    caster.remove_condition("Concentrating")
    assert game.get_entity(dragon.uuid) is None
    assert caster.health.preview_damage(20, DamageType.COLD).applied_damage == 20


SPECIALS = (
    ("air_elemental", PrimordialGales, True, "Shocked"),
    ("air_elemental", GushingAir, False, None),
    ("earth_elemental", SoilCloggedSlam, False, "Prone"),
    ("earth_elemental", SeismicStrike, True, "Trembling Legs"),
    ("fire_elemental", SmoulderingTouch, False, "Burning"),
    ("fire_elemental", CinderousSwipe, False, None),
    ("water_elemental", WaterSlam, False, "Chilled"),
    ("water_elemental", WintersBreath, False, None),
    ("air_myrmidon", ElectrifiedFlail, False, "Stunned"),
    ("earth_myrmidon", GroundedThunder, False, "Prone"),
    ("earth_myrmidon", SludgySling, True, None),
    ("fire_myrmidon", ScorchingStrike, False, "Burning"),
    ("fire_myrmidon", MyrmidonCinderousSwipe, False, None),
    ("water_myrmidon", HiemalStrike, False, "Chilled"),
    ("water_myrmidon", ExplosiveIcicle, False, None),
    ("deva", ConcussiveSmash, False, "Dazed"),
)


@pytest.mark.parametrize(
    "body,kind,centered,status",
    SPECIALS,
    ids=[kind.__name__ for _, kind, _, _ in SPECIALS],
)
def test_special_offense_real_paid_action_damage_and_rider(
    battle, body, kind, centered, status
):
    _, _, _, caster, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    member = summon(battle, body)
    actor = member.entity
    add_modifier(enemy.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name="Easy target", value=-5, source_entity_uuid=enemy.uuid))
    for ability in ("strength", "dexterity", "constitution"):
        force_save_result(enemy, ability, succeeds=False)
    Entity.update_all_entities_senses()
    template = next(
        action for action in actor.registered_actions if isinstance(action, kind)
    )
    selection = {"end_position": actor.position if centered else enemy.position}
    if kind in (
        GushingAir,
        ElectrifiedFlail,
        GroundedThunder,
        ScorchingStrike,
        HiemalStrike,
        ConcussiveSmash,
    ):
        selection = {"target_entity_uuid": enemy.uuid}
    hp = enemy.get_hp()
    with fixed_dice_faces(*([2] * 300)):
        result = template.instantiate(**selection).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert enemy.get_hp() < hp, kind.__name__
    assert actor.action_economy.actions.normalized_score == 0
    if status:
        assert any(
            condition.get_display_name() == status
            for condition in enemy.active_conditions_by_uuid.values()
        ), status


def use(actor, kind, **selection):
    actor.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    template = next(
        action for action in actor.registered_actions if isinstance(action, kind)
    )
    with fixed_dice_faces(*([2] * 300)):
        result = template.instantiate(**selection).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    return result


@pytest.mark.parametrize(
    "kind,position,movement", [(ElementalWarp, (7, 4), 0), (MyrmidonBurrow, (7, 4), 20)]
)
def test_elemental_paid_travel_and_burrow_landing(battle, kind, position, movement):
    _, _, _, _, enemy = battle
    actor = summon(battle, "earth_myrmidon").entity
    Entity.update_entity_position(enemy, (8, 4))
    force_save_result(enemy, "dexterity", succeeds=False)
    hp = enemy.get_hp()
    use(actor, kind, end_position=position)
    assert (
        actor.position == position
        and actor.action_economy.bonus_actions.normalized_score == 0
    )
    assert actor.action_economy.movement_spent() == movement
    if movement:
        assert enemy.get_hp() == hp - 4


def test_muck_to_metal_movement_cost_owned_ac_and_speed_expiry(battle):
    actor = summon(battle, "earth_myrmidon").entity
    use(actor, MuckToMetal)
    assert actor.action_economy.movement_spent() == 17
    assert (
        actor.ac_bonus().normalized_score == 20
        and actor.action_economy.current_speed() == 10
    )
    for _ in range(4):
        actor.on_turn_end()
    assert (
        actor.ac_bonus().normalized_score == 18
        and actor.action_economy.current_speed() == 30
    )


def test_immolation_uses_body_concentration_native_haste_then_lethargy(battle):
    actor = summon(battle, "fire_myrmidon").entity
    use(actor, Immolation)
    assert (
        "Concentrating" in actor.active_conditions
        and "Haste" in actor.active_conditions
    )
    assert (
        actor.ac_bonus().normalized_score == 20
        and actor.action_economy.current_speed() == 60
    )
    actor.remove_condition("Concentrating")
    assert "Haste" not in actor.active_conditions
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.current_speed() == 0


def test_air_innate_invisibility_pays_own_short_rest_resource(battle):
    _, _, _, caster, _ = battle
    actor = summon(battle, "air_myrmidon").entity
    slots = tuple(
        caster.action_economy.spell_slot_value(rank).normalized_score
        for rank in range(1, 10)
    )
    use(actor, Invisibility)
    assert any(
        effect.get_display_name() == "Invisible"
        for effect in actor.active_conditions_by_uuid.values()
    )
    assert not actor.action_economy.can_afford_resource("innate_invisibility", 1)
    assert (
        tuple(
            caster.action_economy.spell_slot_value(rank).normalized_score
            for rank in range(1, 10)
        )
        == slots
    )
    actor.on_short_rest()
    assert actor.action_economy.can_afford_resource("innate_invisibility", 1)


def test_healing_vapours_heals_ally_enemy_and_self_without_poison_exception(battle):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "water_myrmidon").entity
    Entity.update_entity_position(enemy, (5, 2))
    for target in (actor, caster, enemy):
        target.receive_damage(20, DamageType.FORCE, caster.uuid)
    before = {target.uuid: target.get_hp() for target in (actor, caster, enemy)}
    use(actor, HealingVapours, end_position=actor.position)
    assert {
        target.uuid: target.get_hp() - before[target.uuid]
        for target in (actor, caster, enemy)
    } == {target.uuid: 4 for target in (actor, caster, enemy)}
    assert actor.check_condition_immunity("Poisoned")


def test_two_gales_preserve_distinct_restraints_and_body_defeat_cleans_all_fields(
    battle,
):
    game, _, _, caster, enemy = battle
    actor = summon(battle, "djinni").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "strength", succeeds=False)
    use(actor, SweetplumGales, end_position=(5, 2))
    use(actor, SweetplumGales, end_position=(6, 2))
    zones = [
        zone
        for zone in get_map().get_spatial_conditions()
        if isinstance(zone, SweetplumGalesZone)
    ]
    assert len(zones) == 2 and enemy.action_economy.current_speed() == 0
    enemy.move((4, 3))
    assert enemy.action_economy.current_speed() == 0
    actor.receive_damage(1000, DamageType.FORCE, enemy.uuid)
    assert game.get_entity(actor.uuid) is None
    assert not any(
        isinstance(zone, SweetplumGalesZone)
        for zone in get_map().get_spatial_conditions()
    )
    assert enemy.action_economy.current_speed() == 30


def test_vortex_damage_independent_of_deafened_immunity_and_rejected_replacement(
    battle,
):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "air_myrmidon").entity
    Entity.update_entity_position(enemy, (5, 2))
    enemy.add_condition_immunity("Deafened", immunity_name="Test")
    use(actor, RagingVortex, end_position=(5, 2))
    zone = next(
        zone
        for zone in get_map().get_spatial_conditions()
        if isinstance(zone, RagingVortexZone)
    )
    hp = enemy.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        enemy.on_turn_start()
    assert enemy.get_hp() == hp - 4

    def refuse(event, _):
        if isinstance(event, ConditionApplicationEvent) and isinstance(
            event.condition, RagingVortexZone
        ):
            return event.cancel(status_message="Vortex refused")
        return None

    actor.add_event_handler(
        EventHandler(
            name="Reject new vortex",
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.DECLARATION,
                )
            ],
            event_processor=refuse,
        )
    )
    actor.action_economy.reset_all_costs()
    action = next(
        action
        for action in actor.registered_actions
        if isinstance(action, RagingVortex)
    )
    result = action.instantiate(end_position=(6, 2)).apply()
    assert result is not None and result.canceled
    assert get_map().get_spatial_condition(zone.uuid) is zone


def test_cambion_uses_actual_charm_person_to_enable_and_consume_kiss(battle):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "cambion").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "wisdom", succeeds=False)
    use(actor, CharmPerson, target_entity_uuid=enemy.uuid)
    hp = enemy.get_hp()
    use(actor, DrainingKiss, target_entity_uuid=enemy.uuid)
    assert enemy.get_hp() == hp - 15
    assert not any(
        effect.get_display_name() == "Charmed"
        for effect in enemy.active_conditions_by_uuid.values()
    )


def test_winters_breath_cools_burning_then_brittle_ticks_only_cold(battle):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "water_elemental").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "constitution", succeeds=False)
    enemy.add_condition(
        Burning(source_entity_uuid=caster.uuid, target_entity_uuid=enemy.uuid)
    )
    use(actor, WintersBreath, end_position=enemy.position)
    assert (
        "Burning" not in enemy.active_conditions
        and "Brittle" in enemy.active_conditions
    )
    hp = enemy.get_hp()
    with fixed_dice_faces(*([2] * 100)):
        enemy.on_turn_start()
    assert enemy.get_hp() == hp - 4


@pytest.mark.parametrize("key", ["air_elemental", "djinni"])
def test_independent_summon_long_rest_ends_body(battle, key):
    game, _, system, caster, _ = battle
    actor = summon(battle, key).entity
    assert caster.on_long_rest()
    assert game.get_entity(actor.uuid) is None and actor.uuid not in system.memberships


@pytest.mark.parametrize("body", BODIES, ids=lambda body: body.key)
def test_every_body_acts_through_native_autonomous_advance(autonomous_battle, body):
    battle = autonomous_battle
    _, encounter, _, caster, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    add_modifier(enemy.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
            name="Deterministic attack target", value=-10, source_entity_uuid=enemy.uuid
        ))
    if body.key == "cambion":
        enemy.creature_type = CreatureType.UNDEAD
    actor = summon(battle, body.key).entity
    Entity.update_all_entities_senses()
    hp = enemy.get_hp()
    cursor = EventQueue.event_cursor()
    encounter.next_turn()
    assert encounter.get_current_entity() is actor
    for _ in range(8):
        if encounter.get_current_entity() is not actor:
            break
        with fixed_dice_faces(15, *([2] * 150)):
            result = encounter.advance_one_controller_action_boundary()
        if enemy.get_hp() < hp:
            break
        assert result.status == "autonomous_action_completed", (
            body.key,
            str(result),
            [
                (row.behavior_id, row.can_afford, len(row.valid_targets))
                for row in get_available_actions(actor, legal_only=True).all_actions
            ],
        )
    assert enemy.get_hp() < hp, body.key
    assert any(
        event.source_entity_uuid == actor.uuid
        and event.phase is EventPhase.COMPLETION
        and not event.canceled
        for _, event in EventQueue.iter_events_since(cursor)
    ), body.key


def test_dragon_ai_discovers_and_uses_free_breath_after_spending_action(autonomous_battle):
    battle = autonomous_battle
    _, encounter, _, _, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    actor = summon(battle, "draconic_spirit").entity
    encounter.next_turn()
    Entity.update_all_entities_senses()
    multi = next(
        action
        for action in actor.registered_actions
        if isinstance(action, MultiattackAction)
    )
    with fixed_dice_faces(15, *([2] * 100)):
        multi.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert actor.action_economy.actions.normalized_score == 0
    choices = get_available_actions(actor, legal_only=True)
    assert any(
        row.behavior_id == "action.draconic_spirit.breath" and row.can_afford
        for row in choices.all_actions
    )
    cursor = EventQueue.event_cursor()
    for _ in range(4):
        with fixed_dice_faces(*([2] * 100)):
            result = encounter.advance_one_controller_action_boundary()
        events = [
            event
            for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ActionEvent)
            and event.behavior_id == "action.draconic_spirit.breath"
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
        ]
        if events:
            break
        assert result.status == "autonomous_action_completed"
    assert events and actor.action_economy.actions.normalized_score == 0


def test_dragon_late_multiattack_effect_veto_grants_no_breath_or_rend(battle):
    _, _, _, _, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    actor = summon(battle, "draconic_spirit").entity

    def veto(event, _):
        if (
            isinstance(event, ActionEvent)
            and event.behavior_id == "action.monster.multiattack"
        ):
            return event.cancel(status_message="Multiattack refused")
        return None

    actor.add_event_handler(
        EventHandler(
            name="Late root veto",
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=veto,
        )
    )
    multi = next(
        action
        for action in actor.registered_actions
        if isinstance(action, MultiattackAction)
    )
    hp = enemy.get_hp()
    result = multi.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled
    assert enemy.get_hp() == hp
    assert not any(
        isinstance(action, DragonBreath) and action.allowance_uuid is not None
        for action in actor.registered_actions
    )


@pytest.mark.parametrize("critical,expected", [(False, 15), (True, 21)])
def test_grounded_thunder_fixed_nine_not_doubled_on_critical(
    battle, critical, expected
):
    _, _, _, _, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    actor = summon(battle, "earth_myrmidon").entity
    add_modifier(enemy.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name="Easy target", value=-5, source_entity_uuid=enemy.uuid))
    force_save_result(enemy, "constitution", succeeds=True)
    Entity.update_all_entities_senses()
    hp = enemy.get_hp()
    action = next(
        action
        for action in actor.registered_actions
        if isinstance(action, GroundedThunder)
    )
    with fixed_dice_faces(20 if critical else 15, *([2] * 80)):
        result = action.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert enemy.get_hp() == hp - expected


def test_water_slam_typed_fixed_and_cold_packet_affinities(battle):
    _, _, _, _, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    actor = summon(battle, "water_elemental").entity
    add_modifier(enemy.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name="Easy target", value=-5, source_entity_uuid=enemy.uuid))
    enemy.health.nonmagical_attack_resistances = frozenset({DamageType.BLUDGEONING})
    # Intrinsic Water Slam is magical; its fixed packet remains five and Chilled applies after this hit.
    hp = enemy.get_hp()
    use(actor, WaterSlam, end_position=enemy.position)
    assert enemy.get_hp() == hp - 9


@pytest.mark.parametrize("magical,expected", [(False, 5), (True, 10)])
def test_nonmagical_bps_resistance_uses_actual_natural_attack_flag(
    battle, magical, expected
):
    _, _, _, caster, enemy = battle
    target = summon(battle, "earth_elemental").entity
    Entity.update_entity_position(enemy, (5, 2))
    add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name="Easy target", value=-5, source_entity_uuid=target.uuid))
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    action = NaturalAttack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=target.uuid,
        costs=[],
        natural_damage_dice=6,
        natural_dice_numbers=2,
        fixed_damage_bonus=6,
        fixed_attack_bonus=10,
        magical=magical,
        natural_damage_type=DamageType.BLUDGEONING,
    )
    with fixed_dice_faces(15, 2, 2):
        result = action.apply()
    assert result is not None and not result.canceled
    assert target.get_hp() == hp - expected


def test_elemental_multiattack_exhaustion_is_visible_before_second_action(battle):
    _, _, _, _, enemy = battle
    Entity.update_entity_position(enemy, (5, 2))
    actor = summon(battle, "air_elemental").entity
    multi = next(
        action
        for action in actor.registered_actions
        if isinstance(action, MultiattackAction)
    )
    Entity.update_all_entities_senses()
    with fixed_dice_faces(*([15, 2, 2, 2, 2] * 10)):
        result = multi.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    actor.action_economy.reset_all_costs()
    assert not multi.check_costs()


def test_gales_natural_expiry_removes_empty_owner(battle):
    _, encounter, _, _, enemy = battle
    actor = summon(battle, "djinni").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "strength", succeeds=False)
    use(actor, SweetplumGales, end_position=enemy.position)
    while encounter.round_number < 4:
        encounter.next_turn()
    assert not any(
        isinstance(zone, SweetplumGalesZone)
        for zone in get_map().get_spatial_conditions()
    )
    assert not any(
        effect.get_display_name().startswith("Sweetplum Field Owner")
        for effect in actor.active_conditions_by_uuid.values()
    )
    assert enemy.action_economy.current_speed() == 30


def test_deva_innate_revivify_spends_own_long_rest_resource_without_caster_slot(battle):
    game, _, _, caster, enemy = battle
    deva = summon(battle, "deva").entity
    companion = high_actor(game, "Fallen", (3, 3), caster.faction)
    companion.is_player_companion = True
    companion.receive_damage(companion.get_hp(), DamageType.FORCE, enemy.uuid)
    assert companion.health.life_state is LifeState.DEAD
    slots = tuple(
        caster.action_economy.spell_slot_value(rank).normalized_score
        for rank in range(1, 10)
    )
    use(deva, Revivify, target_entity_uuid=companion.uuid)
    assert companion.get_hp() == 1 and companion.health.life_state is LifeState.ALIVE
    assert not deva.action_economy.can_afford_resource("innate_revivify", 1)
    assert (
        tuple(
            caster.action_economy.spell_slot_value(rank).normalized_score
            for rank in range(1, 10)
        )
        == slots
    )


def test_fire_myrmidon_rebuke_uses_own_resource_and_shared_reaction_with_oa(battle):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "fire_myrmidon").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "dexterity", succeeds=False)
    Entity.update_all_entities_senses()
    hp = enemy.get_hp()
    with fixed_dice_faces(*([2] * 100)):
        actor.receive_damage(1, DamageType.FORCE, enemy.uuid)
    assert enemy.get_hp() == hp - 4
    assert actor.action_economy.reactions.normalized_score == 0
    assert not actor.action_economy.can_afford_resource("innate_rebuke", 1)
    hp = enemy.get_hp()
    enemy.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = Move(source_entity_uuid=enemy.uuid, end_position=(6, 2)).apply()
    assert result is not None and not result.canceled and enemy.get_hp() == hp


@pytest.mark.parametrize(
    "color,element",
    [
        ("black", DamageType.ACID),
        ("white", DamageType.COLD),
        ("red", DamageType.FIRE),
        ("blue", DamageType.LIGHTNING),
        ("green", DamageType.POISON),
    ],
)
def test_dragon_color_keeps_innate_resistances_and_matches_breath_and_caster_lease(battle, color, element):
    _, _, _, caster, _ = battle
    member = summon(battle, "draconic_spirit", form_id=color)
    dragon = member.entity
    assert dragon.name == f"{color.title()} Draconic Spirit"
    assert member.existence.origin.recipe.parameters["dragon_color"] == color
    breath, = (action for action in dragon.registered_actions if isinstance(action, DragonBreath))
    assert breath.packets[0].damage_type == element.value
    for kind in (
        DamageType.ACID,
        DamageType.COLD,
        DamageType.FIRE,
        DamageType.LIGHTNING,
        DamageType.POISON,
    ):
        assert dragon.health.preview_damage(20, kind).applied_damage == 10
        assert caster.health.preview_damage(20, kind).applied_damage == (
            10 if kind is element else 20
        )
    caster.remove_condition("Concentrating")
    assert caster.health.preview_damage(20, element).applied_damage == 20


@pytest.mark.parametrize("key", ["breath_type", "shared_resistance"])
@pytest.mark.parametrize("from_template", [False, True], ids=["constructor", "template"])
def test_dragon_rejects_obsolete_independent_element_inputs(battle, key, from_template):
    _, _, system, caster, _ = battle
    values = {"source_entity_uuid": caster.uuid, "form_id": "red", "end_position": (4, 2)}
    with pytest.raises(ValueError):
        if from_template:
            SummonDragon(**values).instantiate(**{key: DamageType.COLD})
        else:
            SummonDragon(**values, **{key: DamageType.COLD})
    assert not system.memberships
    assert caster.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize("enchanted,damage", [(False, 1), (True, 3)])
def test_mundane_weapon_and_magic_weapon_use_conditional_bps_resistance(
    battle, enchanted, damage
):
    _, _, _, _, enemy = battle
    target = summon(battle, "earth_elemental").entity
    Entity.update_entity_position(enemy, (5, 2))
    equip(enemy)
    Entity.update_all_entities_senses()
    if enchanted:
        result = MagicWeapon(
            source_entity_uuid=enemy.uuid,
            target_entity_uuid=enemy.uuid,
            cast_at_level=3,
        ).apply()
        assert result is not None and not result.canceled
        enemy.action_economy.reset_all_costs()
    hp = target.get_hp()
    with fixed_dice_faces(19, 2):
        result = Attack(
            source_entity_uuid=enemy.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and not result.canceled
    assert target.get_hp() == hp - damage
