"""Explicit native scenario composition for new review captures."""

from dnd.core.life_types import LifeState
from devtools.animation_review.control_cases import control_spell_history
from game.combat_demo import capture_combat_demo
from game.replay import CapturedHistory
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history
from tests.game.creature_scenarios import creature_history
from tests.game.concealment_scenarios import concealment_history
from tests.game.discovery_scenarios import discovery_history
from tests.game.device_scenarios import device_history
from tests.game.web_scenarios import web_history
from tests.game.cantrip_scenarios import cantrip_history
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.support_scenarios import support_history
from tests.game.healing_batch_scenarios import healing_batch_history
from tests.game.pending_spell_scenarios import pending_spell_history
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.globe_scenarios import globe_history
from tests.game.projectile_life_scenarios import projectile_life_history
from tests.game.true_strike_scenarios import true_strike_history
from tests.game.dread_residue_scenarios import dread_residue_history
from tests.game.equipment_scenarios import equipment_sequence_history
from tests.game.mechanism_scenarios import mechanism_history
from tests.game.trap_expansion_scenarios import trap_expansion_history
from tests.game.portal_scenarios import portal_history
from tests.game.door_destruction_scenarios import door_destruction_history
from tests.game.trap_hardware_scenarios import trap_hardware_history
from tests.game.prop_destruction_scenarios import prop_destruction_history
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

from devtools.animation_review.cases import (
    AreaSpellCase, CantripCase, AttackCase, BodyResidueCase, CastCase, ConcealmentCase, CreatureCase, DeviceCase, DiscoveryCase, DodgeExpiryCase, DreadResidueCase,
    MechanismCase, PortalCase, DoorCase, TrapHardwareCase, PropDestructionCase, LiquidBarrelCase, EnvironmentCase, EnvironmentControlCase, EquipmentCase, ForcedMovementCase, GroundContactCase, HealingCase, LifecycleCase, MovementCase,
    ParalysisCase, ParalysisLifecycleCase, PendingSpellCase, PersistentSpellCase, GlobeCase, InterruptionCase, ControlSpellCase, ProjectileLifeCase, ReviewCase, SpellHandoffCase, SupportCase, HealingBatchCase, TrueStrikeCase, TeleportCase, TrapCase, VisibilityCase, WebCase,
)


def produce(case: ReviewCase) -> CapturedHistory:
    """Run real rules once, then hand only retained values to the recorder."""
    match case.scenario:
        case GlobeCase() as scenario:
            return globe_history(spell=scenario.spell, protection=scenario.protection,
                source_inside=scenario.source_inside, impact_offset=scenario.impact_offset, walls=scenario.walls)
        case InterruptionCase() as scenario:
            return interruption_history(blocker=scenario.blocker, spell=scenario.spell, blocked=scenario.blocked)
        case PersistentSpellCase() as scenario:
            return persistent_spell_history(program=scenario.program, mode=scenario.mode, energy=scenario.energy,
                saved=scenario.saved, jump=scenario.jump, shield_delivery=scenario.shield_delivery,
                environment=scenario.environment, jump_across=scenario.jump_across, discovered=scenario.discovered,
                cast_level=scenario.cast_level, ward_expiry=scenario.ward_expiry,
                ward_retained=scenario.ward_retained)
        case ControlSpellCase() as scenario:
            return control_spell_history(program=scenario.program, saved=scenario.saved,
                remove_first=scenario.remove_first, repeat_source=scenario.repeat_source)
        case ProjectileLifeCase() as scenario:
            return projectile_life_history(initial=LifeState(scenario.initial), repeated=scenario.repeated)
        case PendingSpellCase() as scenario:
            return pending_spell_history(program=scenario.program, miss=scenario.miss, saved=scenario.saved,
                blocked=scenario.blocked, raised=scenario.raised, long_jump=scenario.long_jump,
                replace_grant=scenario.replace_grant, perspective=scenario.perspective)
        case DoorCase() as scenario:
            return door_destruction_history(item_id=scenario.item_id, program=scenario.program,
                swing=scenario.swing, jammed=scenario.jammed, raised=scenario.raised)
        case TrapHardwareCase() as scenario:
            return trap_hardware_history(item_id=scenario.item_id, deployed=scenario.deployed)
        case PropDestructionCase() as scenario:
            return prop_destruction_history(item_id=scenario.item_id, opened=scenario.opened)
        case LiquidBarrelCase() as scenario:
            return liquid_barrel_history(liquid=scenario.liquid, saved=scenario.saved, jump=scenario.jump,
                layout=scenario.layout, landing=scenario.landing)
        case SupportCase() as scenario:
            return support_history(program=scenario.program, diagonal=scenario.diagonal)
        case HealingBatchCase() as scenario:
            return healing_batch_history(program=scenario.program, self_target=scenario.self_target,
                clean_target=scenario.clean_target)
        case TrueStrikeCase() as scenario:
            return true_strike_history(ranged=scenario.ranged, miss=scenario.miss)
        case CantripCase() as scenario:
            return cantrip_history(program=scenario.program, outcome=scenario.outcome, layout=scenario.layout)
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
            )
        case CreatureCase() as scenario:
            return creature_history(scenario.creature_identity, weapon_slot=scenario.weapon_slot,
                                                seed=scenario.seed)
        case EquipmentCase() as scenario:
            return equipment_sequence_history(replacement=scenario.replacement, attacks=scenario.attacks)
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
                                                behavior=scenario.behavior, boost=scenario.boost)
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
                scenario.seed, scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
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
