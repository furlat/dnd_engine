"""Approved spell ownership repairs through casts and native effect admission."""
from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.monsters.spell_summon_actions import Burning, HealingVapours, WintersBreath
from dnd.monsters.traits import LifeDrainReduction
from dnd.spatial.environmental_conditions import ElectrifiedWater, IceSurface, SteamCloud, Wet, WetSurface, WetAreaCondition, WET_SURFACE_CONTENT_REF
from dnd.spells.abjuration import AuraOfLife, GlyphSleepEffect
from dnd.spells.conjuration import MistyStep
from dnd.spells.enchantment import Feeblemind
from dnd.spells.evocation import HealSpell, ResilientSphere, SearingSmite, SearingSmiteEffect
from dnd.spells.necromancy import Harm, RayOfSicknessPoison
from dnd.spells.surfaces import SimpleToxinSurface, SpellAcidSurface
from dnd.spells.transmutation import CreateOrDestroyWater, Disintegrate
from dnd.spells.wall_constructions import Forcecage
from tests.engine.test_bg3_rank_one_two_spells import game as game
from tests.engine.test_bg3_spell_hit_riders import equip
from tests.engine.test_high_level_spell_controls import cast, conditions, high_actor
from tests.engine.test_high_level_spell_summons import summon, use
from tests.engine.test_summoning_lifecycle import battle as battle
from tests.manual.spell_regression_support import force_save_result


@pytest.mark.parametrize("surface_type", [WetSurface, ElectrifiedWater, IceSurface, SteamCloud, SimpleToxinSurface])
@pytest.mark.parametrize("partial", [False, True])
def test_destroy_water_uses_owned_partial_surface_transitions(game, surface_type, partial):
    caster = high_actor(game)
    cells = {(6, 2), (12, 2) if partial else (7, 2)}
    values = {"spell_dc": 12, "content_ref": get_content_declaration(SimpleToxinSurface).ref} if surface_type is SimpleToxinSurface else {}
    surface = surface_type(source_entity_uuid=caster.uuid, position=(6, 2),
                           affected_positions=cells, **values)
    assert surface.activate(parent_event=None) is not None and surface.applied
    acid = SpellAcidSurface(source_entity_uuid=caster.uuid, position=(6, 2), affected_positions={(6, 2)}, content_ref=get_content_declaration(SpellAcidSurface).ref)
    assert acid.activate(parent_event=None) is not None and acid.applied
    cast(CreateOrDestroyWater, caster, end_position=(5, 2), mode="destroy")
    assert surface.applied is partial
    if partial:
        assert surface.affected_positions == {(12, 2)}
    assert acid.applied and acid.affected_positions == {(6, 2)}


def test_destroy_water_transition_veto_preserves_surface(game):
    caster = high_actor(game)
    surface = WetSurface(source_entity_uuid=caster.uuid, position=(6, 2), affected_positions={(6, 2)})
    surface.activate(parent_event=None)
    def veto(event, _):
        if event.operation.value == "dry":
            return event.cancel(status_message="Drying refused")
    caster.add_event_handler(EventHandler(name="Drying admission veto", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_EFFECT_INTERACTION, event_phase=EventPhase.EXECUTION)],
        event_processor=veto))
    cast(CreateOrDestroyWater, caster, end_position=(5, 2), mode="destroy")
    assert surface.applied and surface.affected_positions == {(6, 2)}


@pytest.mark.parametrize("burn_type", [SearingSmiteEffect, Burning])
def test_active_wet_owns_admission_without_changing_sleep_rule(game, burn_type):
    caster = high_actor(game)
    target = high_actor(game, "Wet recipient", (3, 2))
    left = Wet(name="First water lease", source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    right = Wet(name="Second water lease", source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(left)
    target.add_condition(right)
    target.remove_condition_by_uuid(left.uuid)
    extra = {"spell_dc": 15} if burn_type is SearingSmiteEffect else {}
    burn = burn_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, **extra)
    result = target.add_condition(burn)
    assert result is not None and result.canceled and not burn.applied
    sleep = GlyphSleepEffect(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    result = target.add_condition(sleep)
    assert result is not None and not result.canceled and sleep.applied
    target.remove_condition_by_uuid(sleep.uuid)
    target.remove_condition_by_uuid(right.uuid)
    burn = burn_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, **extra)
    result = target.add_condition(burn)
    assert result is not None and not result.canceled and burn.applied
    target.add_condition(Wet(name="New water", source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    assert not burn.applied


def test_searing_smite_immediate_weapon_and_fire_damage_still_hits_wet(game):
    caster = high_actor(game)
    target = high_actor(game, "Enemy", (3, 2), "foes")
    equip(caster)
    target.add_condition(Wet(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    before = target.get_hp()
    with fixed_dice_faces(15, *([2] * 20)):
        cast(SearingSmite, caster, target)
    assert target.get_hp() < before
    assert "Searing Smite Burn" not in conditions(target)
    assert caster.action_economy.spell_slot_1.normalized_score == 3


@pytest.mark.parametrize("veto_phase", [None, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_sphere_destruction_waits_for_accepted_disintegrate(game, veto_phase):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (3, 2))
    attacker = high_actor(game, "Ray caster", (4, 2), "foes")
    cast(ResilientSphere, caster, target)
    before = target.get_hp()
    if veto_phase is not None:
        def veto(event, _):
            if isinstance(event, SpellEvent) and event.spell_id == "disintegrate":
                return event.cancel(status_message="Ray admission refused")
        attacker.add_event_handler(EventHandler(name="Late ray veto", source_entity_uuid=attacker.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL,event_phase=veto_phase)],event_processor=veto))
    result = Disintegrate(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None
    assert target.get_hp() == before
    assert ("Resilient Sphere" in conditions(target)) is (veto_phase is not None)
    assert attacker.action_economy.actions.normalized_score == 0
    assert attacker.action_economy.spell_slot_6.normalized_score == 3


def test_sphere_native_removal_rejection_keeps_occupant_protected(game):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (3, 2))
    attacker = high_actor(game, "Ray caster", (4, 2), "foes")
    cast(ResilientSphere, caster, target)
    sphere = conditions(target)["Resilient Sphere"]
    def veto(event, _):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == sphere.uuid:
            return event.cancel(status_message="Enclosure retirement refused")
    target.add_event_handler(EventHandler(name="Sphere removal veto", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,event_phase=EventPhase.DECLARATION)],
        event_processor=veto))
    before = target.get_hp()
    cast(Disintegrate, attacker, target)
    assert sphere.applied and target.get_hp() == before


@pytest.mark.parametrize("veto_phase", [None, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_feeblemind_accepted_heal_cures_even_at_full_hp(game, veto_phase):
    caster = high_actor(game)
    target = high_actor(game, "Victim", (3, 2), "foes")
    force_save_result(target, "intelligence", succeeds=False)
    cast(Feeblemind, caster, target)
    target.receive_healing(1000, caster.uuid)
    assert target.get_hp() == target.get_max_hp() and "Feeblemind" in conditions(target)
    caster.action_economy.reset_all_costs()
    if veto_phase is not None:
        def veto(event, _):
            if isinstance(event, SpellEvent) and event.spell_id == "heal":
                return event.cancel(status_message="Heal admission refused")
        caster.add_event_handler(EventHandler(name="Heal veto", source_entity_uuid=caster.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL,event_phase=veto_phase)],event_processor=veto))
    result = HealSpell(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None
    assert ("Feeblemind" in conditions(target)) is (veto_phase is not None)
    assert target.get_hp() == target.get_max_hp()


def test_aura_life_admits_all_actual_reduction_producers_and_repeated_loss(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    foe = high_actor(game, "Foe", (4, 2), "foes")
    drain = LifeDrainReduction(source_entity_uuid=foe.uuid,target_entity_uuid=ally.uuid,amount=10)
    ally.add_condition(drain)
    maximum = ally.get_max_hp()
    cast(AuraOfLife, caster)
    cause = Event(source_entity_uuid=foe.uuid,event_type=EventType.BASE_ACTION)
    drain.add_reduction(5, cause)
    force_save_result(ally, "constitution", succeeds=False)
    with fixed_dice_faces(*([2] * 40)):
        cast(Harm, foe, ally)
    assert ally.get_max_hp() == maximum and "Harm" not in conditions(ally)
    assert drain.amount == 10
    ally.move((12, 2))
    drain.add_reduction(5, cause)
    assert ally.get_max_hp() == maximum - 5 and drain.amount == 15


class OtherNativeTeleport(MistyStep):
    name: str = "Authored transfer test"


def test_forcecage_uses_transfer_fact_instead_of_spell_name(game):
    caster = high_actor(game)
    prisoner = high_actor(game, "Prisoner", (8, 4), "foes")
    cast(Forcecage, caster, end_position=(8, 4), cage_form="box")
    force_save_result(prisoner, "charisma", succeeds=False)
    result = OtherNativeTeleport(source_entity_uuid=prisoner.uuid,end_position=(11, 4)).apply()
    assert result is not None and prisoner.position == (8, 4)
    assert prisoner.action_economy.spell_slot_2.normalized_score == 3
    prisoner.action_economy.reset_all_costs()
    force_save_result(prisoner, "charisma", succeeds=True)
    force_save_result(prisoner, "charisma", succeeds=True)
    result = OtherNativeTeleport(source_entity_uuid=prisoner.uuid,end_position=(11, 4)).apply()
    assert result is not None and not result.canceled and prisoner.position == (11, 4)


@pytest.mark.parametrize("saved", [False, True])
def test_winters_breath_uses_stable_burning_identity_after_relabel(battle, saved):
    _, _, _, caster, enemy = battle
    actor = summon(battle, "water_elemental").entity
    Entity.update_entity_position(enemy, (5, 2))
    force_save_result(enemy, "constitution", succeeds=saved)
    burn = Burning(name="Relabeled fire status",source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid)
    enemy.add_condition(burn)
    use(actor, WintersBreath, end_position=enemy.position)
    assert not burn.applied
    assert ("Brittle" in enemy.active_conditions) is (not saved)


def test_named_interactions_use_authored_spell_identity_after_relabel(game):
    caster = high_actor(game)
    target = high_actor(game, "Inside", (3, 2))
    attacker = high_actor(game, "Attacker", (4, 2), "foes")
    cast(ResilientSphere, caster, target)
    hp = target.get_hp()
    cast(Disintegrate, attacker, target, name="Relabeled ray")
    assert target.get_hp() == hp and "Resilient Sphere" not in conditions(target)
    force_save_result(target, "intelligence", succeeds=False)
    cast(Feeblemind, attacker, target)
    cast(HealSpell, caster, target, name="Relabeled curative cast")
    assert "Feeblemind" not in conditions(target)


def test_healing_vapours_recognizes_relabeled_poisoned_source(game):
    actor = high_actor(game)
    target = high_actor(game, "Recipient", (3, 2))
    poison = RayOfSicknessPoison(name="Renamed poison",source_entity_uuid=target.uuid,target_entity_uuid=actor.uuid)
    actor.add_condition(poison)
    assert poison.applied
    hp = target.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        result = HealingVapours(source_entity_uuid=actor.uuid,end_position=actor.position).apply()
    assert result is not None and not result.canceled
    assert target.get_hp() == hp - 4


def test_independent_new_water_owners_dry_individually_and_respect_native_veto(game):
    caster = high_actor(game)
    first = WetAreaCondition(name="New water owner",source_entity_uuid=caster.uuid,position=(6, 2),
        affected_positions={(6, 2)},content_ref=WET_SURFACE_CONTENT_REF,
        layer=SpatialEffectLayer.GROUND_SURFACE,occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING)
    second = WetAreaCondition(name="Independent water owner",source_entity_uuid=caster.uuid,position=(6, 2),
        affected_positions={(6, 2)},content_ref=WET_SURFACE_CONTENT_REF,
        layer=SpatialEffectLayer.GROUND_SURFACE,occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING)
    first.activate(parent_event=None)
    second.activate(parent_event=None)
    assert first.applied and second.applied
    def veto(event, _):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == first.uuid:
            return event.cancel(status_message="One native water removal refused")
    caster.add_event_handler(EventHandler(name="One surface veto",source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,event_phase=EventPhase.DECLARATION)],
        event_processor=veto))
    cast(CreateOrDestroyWater,caster,end_position=(5, 2),mode="destroy")
    assert first.applied and not second.applied


def test_aura_removal_restores_reduction_admission(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    foe = high_actor(game, "Foe", (4, 2), "foes")
    drain = LifeDrainReduction(source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid, amount=10)
    ally.add_condition(drain)
    cast(AuraOfLife, caster)
    maximum = ally.get_max_hp()
    cause = Event(source_entity_uuid=foe.uuid, event_type=EventType.BASE_ACTION)
    drain.add_reduction(3, cause)
    current = ally.get_max_hp()
    assert current == maximum
    caster.remove_condition("Concentrating")
    drain.add_reduction(3, cause)
    current = ally.get_max_hp()
    assert current == maximum - 3
