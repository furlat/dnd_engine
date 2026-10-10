"""Explicit native scenario composition for new review captures."""

from dnd.core.life_types import LifeState
from dnd.types.materials import Material
from devtools.animation_review.cases import SolidWallCase
from tests.game.solid_wall_scenarios import solid_wall_history
from devtools.animation_review.summoning_cases import summoning_history
from devtools.animation_review.flight_cases import fly_lifetime_history
from devtools.animation_review.creature_spell_cases import creature_spell_history
from devtools.animation_review.control_cases import control_spell_history
from game.combat_demo import capture_combat_demo
from dnd.player.recorded import CapturedHistory
from tests.game.curse_scenarios import curse_history
from devtools.animation_review.curse_cases import CurseCase
from devtools.animation_review.divine_cases import DivineCase
from tests.game.divine_scenarios import divine_history
from tests.game.power_word_scenarios import power_word_history
from tests.game.nature_spell_scenarios import nature_spell_history
from tests.game.directed_spell_scenarios import directed_spell_history
from tests.game.necrotic_spell_scenarios import necrotic_spell_history
from tests.game.antimagic_scenarios import antimagic_history
from tests.game.transport_spell_scenarios import transport_spell_history
from tests.game.electric_spell_scenarios import electric_spell_history
from tests.game.weather_solar_scenarios import weather_solar_history
from tests.game.holy_spell_scenarios import holy_spell_history
from devtools.animation_review.holy_cases import HolyCase
from devtools.animation_review.class_cases import ClassFeatureCase
from tests.game.class_feature_scenarios import class_feature_history
from devtools.animation_review.weather_solar_cases import WeatherSolarCase
from tests.game.shared_condition_scenarios import shared_condition_history
from devtools.animation_review.slow_cases import SlowCase
from devtools.animation_review.hold_cases import HoldCase
from tests.game.hold_scenarios import hold_history
from devtools.animation_review.fear_cases import FearCase
from devtools.animation_review.hypnotic_cases import HypnoticCase
from devtools.animation_review.assembly_cases import AssemblyCase
from tests.game.assembly_scenarios import assembly_history
from tests.game.hypnotic_scenarios import hypnotic_history
from devtools.animation_review.scorching_cases import ScorchingCase
from tests.game.fear_scenarios import fear_history
from tests.game.scorching_scenarios import scorching_history
from tests.game.slow_scenarios import slow_history
from devtools.animation_review.continual_flame_cases import ContinualFlameCase
from tests.game.continual_flame_scenarios import continual_flame_history
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history
from tests.game.creature_scenarios import creature_history
from tests.game.concealment_scenarios import concealment_history
from tests.game.discovery_scenarios import discovery_history
from tests.game.device_scenarios import device_history
from tests.game.web_scenarios import web_history
from tests.game.cantrip_scenarios import cantrip_history
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.production_gap_scenarios import cone_gap_history, wind_interception_history
from tests.game.support_scenarios import support_history
from tests.game.healing_batch_scenarios import healing_batch_history
from tests.game.support_conditions_scenarios import support_condition_history
from tests.game.pending_spell_scenarios import pending_spell_history
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.wall_spell_scenarios import wall_spell_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.globe_scenarios import globe_history
from tests.game.projectile_life_scenarios import projectile_life_history
from tests.game.true_strike_scenarios import true_strike_history
from tests.game.dread_residue_scenarios import dread_residue_history
from tests.game.equipment_scenarios import equipment_sequence_history
from tests.game.item_appearance_scenarios import item_transfer_history, item_power_history
from tests.game.mechanism_scenarios import mechanism_history
from tests.game.trap_expansion_scenarios import trap_expansion_history
from tests.game.portal_scenarios import portal_history
from tests.game.door_destruction_scenarios import door_destruction_history
from tests.game.window_scenarios import window_history
from tests.game.trap_hardware_scenarios import trap_hardware_history
from tests.game.prop_destruction_scenarios import prop_destruction_history
from tests.game.object_attack_scenarios import object_attack_history
from tests.game.liquid_barrel_scenarios import liquid_barrel_history
from tests.game.environment_scenarios import environment_history
from tests.game.environment_control_scenarios import control_history
from tests.game.forced_movement_scenarios import forced_movement_history
from tests.game.ground_contact_scenarios import ground_contact_history
from tests.game.movement_scenarios import movement_history
from tests.game.teleport_scenarios import teleport_history
from tests.game.spell_handoff_scenarios import spell_handoff_history
from tests.game.trap_scenarios import trap_history
from tests.game.visibility_scenarios import visibility_history
from tests.game.scenarios import (
    attack_history, dodge_expiry_history, healing_history, lifecycle_history, movement_with_paralysis, paralysis_lifecycle,
)
from tests.game.damage_resolution_scenarios import resolution_history, unseen_source_damage
from tests.game.construction_scenarios import construction_history
from tests.game.surface_ignition_scenarios import surface_ignition_history
from tests.game.movement_scenarios import flight_history
from dnd.player.capture import reduce_interval

from devtools.animation_review.cases import (
    ConeOfColdCase, WindInterceptionCase, SummoningCase, AreaSpellCase, CallLightningCase, CantripCase, AttackCase, DamageResolutionCase, ConstructionCase, SurfaceIgnitionCase, FlightCase, ItemPowerCase, BodyResidueCase, CastCase, ConcealmentCase, CreatureCase, DeviceCase, DiscoveryCase, DodgeExpiryCase, DreadResidueCase,
    DirectedSpellCase, TransportSpellCase, AntimagicCase, ElectricSpellCase, NecroticSpellCase, NatureSpellCase, PowerWordCase, SharedConditionCase, MechanismCase, PortalCase, WindowCase, DoorCase, TrapHardwareCase, PropDestructionCase, ObjectAttackCase, LiquidBarrelCase, EnvironmentCase, EnvironmentControlCase, EquipmentCase, ItemTransferCase, ForcedMovementCase, GroundContactCase, HealingCase, LifecycleCase, MovementCase,
    ParalysisCase, ParalysisLifecycleCase, PendingSpellCase, PersistentSpellCase, WallSpellCase, GlobeCase, InterruptionCase, ControlSpellCase, ProjectileLifeCase, ReviewCase, SpellHandoffCase, SupportCase, HealingBatchCase, SupportConditionCase, TrueStrikeCase, TeleportCase, TrapCase, VisibilityCase, WebCase,
)


def produce(case: ReviewCase) -> CapturedHistory:
    """Run real rules once, then hand only retained values to the recorder."""
    match case.scenario:
        case SummoningCase() as scenario:
            return summoning_history(form=scenario.form, family=scenario.family, slot=scenario.slot,
                flight=scenario.flight, release_control=scenario.release_control, program=scenario.program)
        case DamageResolutionCase() as scenario:
            native = (unseen_source_damage(temporary_hp=5, undisclosed_owner=True)[0]
                      if scenario.program == "hidden" else resolution_history(scenario.program))
            before, _ = reduce_interval(None, native.initialization)
            return CapturedHistory(native.initialization, before, native.lineages)
        case ConstructionCase() as scenario:
            return construction_history(material=scenario.material,break_section=scenario.break_section,
                disintegrate=scenario.disintegrate,fracture_after_cut=scenario.fracture_after_cut,dome_radius=scenario.dome_radius)
        case SurfaceIgnitionCase():
            return surface_ignition_history()
        case FlightCase() as scenario:
            return (flight_history() if scenario.recipient is None
                    else fly_lifetime_history(recipient=scenario.recipient, geometry=scenario.geometry))
        case ItemPowerCase():
            return item_power_history()
        case AssemblyCase() as scenario:
            return assembly_history(program=scenario.program,direction=scenario.direction,form=scenario.form)
        case ScorchingCase() as scenario:
            return scorching_history(direction=scenario.direction,split=scenario.split,miss=scenario.miss)
        case HypnoticCase() as scenario:
            return hypnotic_history(mode=scenario.mode)
        case FearCase() as scenario:
            return fear_history(direction=scenario.direction)
        case ContinualFlameCase():
            return continual_flame_history()
        case CurseCase() as scenario:
            return curse_history(option=scenario.option, saved=scenario.saved)
        case HoldCase() as scenario:
            return hold_history(program=scenario.program, saved=scenario.saved,
                retain_paralysis=scenario.retain_paralysis, size_change=scenario.size_change)
        case SlowCase() as scenario:
            return slow_history(saved=scenario.saved)
        case SharedConditionCase() as scenario:
            return shared_condition_history(program=scenario.program, prior=scenario.prior)
        case AntimagicCase():
            return antimagic_history()
        case TransportSpellCase() as scenario:
            return transport_spell_history(program=scenario.program)
        case DirectedSpellCase() as scenario:
            return directed_spell_history(program=scenario.program,mode=scenario.mode,repeat=scenario.repeat,
                saved=scenario.saved,cleanup=scenario.cleanup,lethal=scenario.lethal,prone=scenario.prone,
                magical_weapon=scenario.magical_weapon,target_item_id=scenario.target_item_id)
        case ElectricSpellCase() as scenario:
            return electric_spell_history(program=scenario.program, empty=scenario.empty)
        case NecroticSpellCase() as scenario:
            return necrotic_spell_history(program=scenario.program, saved=scenario.saved, immune=scenario.immune)
        case ClassFeatureCase() as scenario:
            return class_feature_history(program=scenario.program,succeeded=scenario.succeeded,hidden_owner=scenario.hidden_owner,martial_route=scenario.martial_route,retire=scenario.retire)
        case HolyCase() as scenario:
            return holy_spell_history(program=scenario.program,immune=scenario.immune,expire=scenario.expire)
        case WeatherSolarCase() as scenario:
            return weather_solar_history(program=scenario.program, empty=scenario.empty,
                expire=scenario.expire, heading=scenario.heading, repeat=scenario.repeat,
                caster_position=scenario.caster_position)
        case NatureSpellCase() as scenario:
            return nature_spell_history(program=scenario.program, immune=scenario.immune)
        case PowerWordCase() as scenario:
            return power_word_history(program=scenario.program, outcome=scenario.outcome)
        case DivineCase() as scenario:
            return divine_history(program=scenario.program, multiple_targets=scenario.multiple_targets)
        case WallSpellCase() as scenario:
            return wall_spell_history(axis=scenario.axis, raised=scenario.raised,
                retain_field=scenario.retain_field, multiple_targets=scenario.multiple_targets,
                formation_targets=scenario.formation_targets, ring_hot_side=scenario.ring_hot_side)
        case ObjectAttackCase() as scenario:
            return object_attack_history(program=scenario.program)
        case GlobeCase() as scenario:
            return globe_history(spell=scenario.spell, protection=scenario.protection,
                source_inside=scenario.source_inside, impact_offset=scenario.impact_offset, walls=scenario.walls,
                retain_field=scenario.retain_field)
        case InterruptionCase() as scenario:
            return interruption_history(blocker=scenario.blocker, spell=scenario.spell, blocked=scenario.blocked)
        case PersistentSpellCase() as scenario:
            return persistent_spell_history(program=scenario.program, mode=scenario.mode, energy=scenario.energy,
                saved=scenario.saved, jump=scenario.jump, shield_delivery=scenario.shield_delivery,
                environment=scenario.environment, jump_across=scenario.jump_across, discovered=scenario.discovered,
                cast_level=scenario.cast_level, ward_expiry=scenario.ward_expiry,
                ward_retained=scenario.ward_retained, retain_field=scenario.retain_field)
        case ControlSpellCase() as scenario:
            return control_spell_history(program=scenario.program, saved=scenario.saved,
                remove_first=scenario.remove_first, repeat_source=scenario.repeat_source)
        case ProjectileLifeCase() as scenario:
            return projectile_life_history(initial=LifeState(scenario.initial), repeated=scenario.repeated)
        case PendingSpellCase() as scenario:
            return pending_spell_history(program=scenario.program, miss=scenario.miss, saved=scenario.saved,
                blocked=scenario.blocked, raised=scenario.raised, long_jump=scenario.long_jump,
                replace_grant=scenario.replace_grant, perspective=scenario.perspective)
        case WindowCase() as scenario:
            return window_history(family=scenario.family, program=scenario.program)
        case SolidWallCase() as scenario:
            return solid_wall_history(scenario.item_id, material=Material(scenario.material),
                raised=scenario.raised, corner=scenario.corner)
        case DoorCase() as scenario:
            return door_destruction_history(item_id=scenario.item_id, program=scenario.program,
                swing=scenario.swing, jammed=scenario.jammed, raised=scenario.raised)
        case TrapHardwareCase() as scenario:
            return trap_hardware_history(item_id=scenario.item_id, deployed=scenario.deployed)
        case PropDestructionCase() as scenario:
            return prop_destruction_history(item_id=scenario.item_id, opened=scenario.opened,
                                            elevation=scenario.elevation, access=scenario.access)
        case LiquidBarrelCase() as scenario:
            return liquid_barrel_history(liquid=scenario.liquid, saved=scenario.saved, jump=scenario.jump,
                layout=scenario.layout, landing=scenario.landing)
        case SupportCase() as scenario:
            return support_history(program=scenario.program, diagonal=scenario.diagonal)
        case HealingBatchCase() as scenario:
            return healing_batch_history(program=scenario.program, self_target=scenario.self_target,
                clean_target=scenario.clean_target, recovery_condition=scenario.recovery_condition)
        case SupportConditionCase() as scenario:
            return support_condition_history(program=scenario.program, self_target=scenario.self_target,
                ability=scenario.ability, mode=scenario.mode)
        case TrueStrikeCase() as scenario:
            return true_strike_history(ranged=scenario.ranged, miss=scenario.miss)
        case CantripCase() as scenario:
            return cantrip_history(program=scenario.program, outcome=scenario.outcome, layout=scenario.layout)
        case CallLightningCase() as scenario:
            return area_spell_history(program="call_lightning", call_repeat_position=scenario.repeat_position,
                move_before_repeat=scenario.move_before_repeat)
        case ConeOfColdCase() as scenario:
            return cone_gap_history(heading=scenario.heading, oblique=scenario.oblique)
        case WindInterceptionCase() as scenario:
            return wind_interception_history(direction=scenario.direction, blocked=scenario.blocked)
        case AreaSpellCase() as scenario:
            return area_spell_history(program=scenario.program, diagonal=scenario.diagonal, blocked=scenario.blocked)
        case WebCase() as scenario:
            return web_history(delivery=scenario.delivery)
        case DeviceCase() as scenario:
            return device_history(program=scenario.program, wake_damage=scenario.wake_damage)
        case SpellHandoffCase() as scenario:
            return spell_handoff_history(program=scenario.program, level=scenario.level,
                split=scenario.split, miss=scenario.miss, environment=scenario.environment,
                empty=scenario.empty, repeat=scenario.repeat)
        case DreadResidueCase() as scenario:
            return dread_residue_history(entry=scenario.entry)
        case BodyResidueCase() as scenario:
            if scenario.program != "injuries":
                return hidden_residue_history(first_sight=scenario.program == "first-sight")
            return body_residue_history(profile=scenario.profile, mixed=scenario.mixed,
                weapon=scenario.weapon, critical=scenario.critical, hits=scenario.hits,
                layout=scenario.layout, crossings=scenario.crossings, fixed_skeleton=scenario.fixed_skeleton,
                creature_identity=scenario.creature_identity)
        case GroundContactCase() as scenario:
            return ground_contact_history(program=scenario.program)
        case PortalCase() as scenario:
            return portal_history(program=scenario.program, arrival_spikes=scenario.arrival_spikes)
        case MechanismCase() as scenario:
            if scenario.program in ("jaw", "gas", "tripwire"):
                return trap_expansion_history(program=scenario.program, jump=scenario.jump, save=scenario.save)
            return mechanism_history(program=scenario.program, jump=scenario.jump, save=scenario.save,
                hidden_launcher=scenario.hidden_launcher, jump_release=scenario.jump_release)
        case TrapCase() as scenario:
            return trap_history(detected=scenario.detected, payload=scenario.payload,
                save_face=scenario.save_face, bloodied=scenario.bloodied)
        case TeleportCase() as scenario:
            return teleport_history(battlefield_id=scenario.battlefield_id,
                caster_position=scenario.caster_position, witness_position=scenario.witness_position,
                destination=scenario.destination)
        case EnvironmentControlCase() as scenario:
            return control_history(program=scenario.program, hidden_light=scenario.hidden_light,
                observer_darkvision=scenario.observer_darkvision)
        case EnvironmentCase() as scenario:
            return environment_history(program=scenario.program, fixture_kind=scenario.fixture_kind,
                observer_darkvision=scenario.observer_darkvision, second_light=scenario.second_light)
        case ForcedMovementCase() as scenario:
            return forced_movement_history(
                source_position=scenario.source_position, target_position=scenario.target_position,
                battlefield_id=scenario.battlefield_id, seed=scenario.seed,
                blocker_position=scenario.blocker_position, watcher_position=scenario.watcher_position,
                target_identity=scenario.target_identity, target_hp=scenario.target_hp,
                mechanism=scenario.mechanism, destination=scenario.destination,
                initial_cast=scenario.initial_cast, resisted=scenario.resisted, allied=scenario.allied,
            )
        case CreatureCase() as scenario:
            if scenario.spell is not None:
                return creature_spell_history(scenario.creature_identity, spell=scenario.spell)
            return creature_history(scenario.creature_identity, weapon_slot=scenario.weapon_slot,
                                                seed=scenario.seed, multiattack=scenario.multiattack)
        case EquipmentCase() as scenario:
            return equipment_sequence_history(replacement=scenario.replacement, attacks=scenario.attacks)
        case ItemTransferCase() as scenario:
            return item_transfer_history(include_floor_robe=False, initial_hand=scenario.initial_hand,
                                         drop_position=(3, 4), roster_outfit=scenario.roster_outfit,
                                         roster_backpack=scenario.roster_backpack,
                                         weapon_item_id=scenario.weapon_item_id,
                                         coating_item_id=scenario.coating_item_id)[3]
        case DiscoveryCase() as scenario:
            return discovery_history(mode=scenario.mode)
        case VisibilityCase() as scenario:
            return visibility_history(battlefield_id=scenario.battlefield_id,
                observer_position=scenario.observer_position, subject_position=scenario.subject_position,
                route=scenario.route, hidden_change_after=scenario.hidden_change_after, dash_before=scenario.dash_before)
        case ConcealmentCase() as scenario:
            return concealment_history(program=scenario.program, allied=scenario.allied,
                sight_grant=scenario.sight_grant, stealth_face=scenario.stealth_face, reveal=scenario.reveal)
        case MovementCase() as scenario:
            return movement_history(route=scenario.route, battlefield_id=scenario.battlefield_id,
                                                behavior=scenario.behavior, boost=scenario.boost, flight=scenario.flight)
        case AttackCase() as scenario:
            return attack_history(
                scenario.weapon, scenario.seed, opportunity=scenario.opportunity,
                whole_movement=scenario.opportunity, destination=scenario.destination, bloodied=scenario.bloodied,
                maximum_hp=scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
                watcher_positions=scenario.watcher_positions, weapon_slot=scenario.weapon_slot,
                goblin_source=scenario.goblin_source, uses_death_saves=scenario.uses_death_saves,
            )
        case ParalysisCase() as scenario:
            return movement_with_paralysis(
                scenario.seed, scenario.maximum_hp, movement_behavior=scenario.movement_behavior, flight=scenario.flight,
            )
        case ParalysisLifecycleCase() as scenario:
            return paralysis_lifecycle(
                repeat_save_seeds=scenario.repeat_save_seeds,
                movement_behavior=scenario.movement_behavior, resume=scenario.resume,
            )
        case DodgeExpiryCase():
            return dodge_expiry_history()
        case HealingCase() as scenario:
            return healing_history(dying=scenario.dying)
        case LifecycleCase() as scenario:
            return lifecycle_history(save_seeds=scenario.save_seeds,
                heal_after=scenario.heal_after, revive_after=scenario.revive_after)
        case CastCase() as scenario:
            return capture_combat_demo(
                caster_position=scenario.caster_position, second_attack_seed=scenario.second_attack_seed,
                goblin_recipient=scenario.goblin_recipient, replace_weapon=scenario.replace_weapon,
                magic_missile=scenario.magic_missile,
            )
