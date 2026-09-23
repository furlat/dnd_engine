"""Actual spell-owned weapon attacks, recorded once for both participants."""

import random
from uuid import uuid4

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import register_true_strike
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def true_strike_history(*, ranged: bool = False, miss: bool = False,
                        weapon: str = "weapon.shortsword") -> CapturedHistory:
    """The default weapon is a shortsword, or a shortbow for the ranged case.

    A different weapon selects a real equipment fixture, never an animation.
    Ranged targets are twenty feet away, exercising the registered weapon range.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        actors = {}
        selected_weapon = "weapon.shortbow" if ranged and weapon == "weapon.shortsword" else weapon
        slot = WeaponSlot.RANGED_MAIN if ranged else WeaponSlot.MELEE_MAIN
        for role, position in (("caster", (3, 6)), ("recipient", (7 if ranged else 4, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=10), dexterity=AbilityConfig(ability_score=10)),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=6, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
                (build_authored_item(selected_weapon, actor.uuid), slot),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_true_strike(actor, caster_level=5)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="True Strike weapon delivery", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="True Strike initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        choices = [(action, target) for action in get_available_actions(caster).all_actions
                   if action.behavior_id == "spell.true_strike"
                   for target in action.valid_targets if target.target_uuid == recipient.uuid]
        assert len(choices) == 1
        if ranged:
            assert choices[0][1].distance == 20
        actions = caster.action_economy.actions.normalized_score
        bonus_actions = caster.action_economy.bonus_actions.normalized_score
        original_extra = tuple(caster.equipment.extra_attack_damage_type)
        with fixed_dice_faces(*((1,) if miss else (15, 4, 4))):
            result = execute_available_action(caster, *choices[0])
        assert isinstance(result, SpellEvent) and result.phase is EventPhase.COMPLETION and not result.canceled
        assert caster.action_economy.actions.normalized_score == actions - 1
        assert caster.action_economy.bonus_actions.normalized_score == bonus_actions
        assert tuple(caster.equipment.extra_attack_damage_type) == original_extra
        attacks = [event for _, event in EventQueue.iter_events_since(baseline)
                   if isinstance(event, AttackEvent) and event.phase is EventPhase.COMPLETION]
        assert len(attacks) == 1 and attacks[0].attack_outcome is (
            AttackOutcome.CRIT_MISS if miss else AttackOutcome.HIT)
        assert recipient.get_hp() == 60 - (0 if miss else 12)
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        view = captured.views["caster"]
        return CapturedHistory(view.initialization, before, view.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
