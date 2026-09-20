"""Explicit native scenario composition for new review captures."""

from game.combat_demo import capture_combat_demo
from game.replay import CapturedHistory
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history
from tests.game.creature_scenarios import creature_history
from tests.game.concealment_scenarios import concealment_history
from tests.game.discovery_scenarios import discovery_history
from tests.game.dread_residue_scenarios import dread_residue_history
from tests.game.equipment_scenarios import equipment_sequence_history
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
    AttackCase, BodyResidueCase, CastCase, ConcealmentCase, CreatureCase, DiscoveryCase, DodgeExpiryCase, DreadResidueCase,
    EnvironmentCase, EnvironmentControlCase, EquipmentCase, ForcedMovementCase, GroundContactCase, HealingCase, LifecycleCase, MovementCase,
    ParalysisCase, ParalysisLifecycleCase, ReviewCase, SpellHandoffCase, TeleportCase, TrapCase, VisibilityCase,
)


def produce(case: ReviewCase) -> CapturedHistory:
    """Run real rules once, then hand only retained values to the recorder."""
    match case.scenario:
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
