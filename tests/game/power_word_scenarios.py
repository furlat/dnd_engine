"""Real Power Word outcomes, including threshold failures and death prevention."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Prone
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import BodyPart
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import DeathWardEffect
from dnd.spells.enchantment import PowerWordKill, PowerWordStun
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def power_word_history(*, program: Literal["kill", "stun"],
                       outcome: Literal["applied", "threshold", "ward", "prone", "immune"] = "applied") -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (("caster", (4, 6)), ("recipient", (6, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes" if role == "caster" else "enemies",
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={8: 2, 9: 2}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")])))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, PowerWordKill if program == "kill" else PowerWordStun, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, target = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Power Word outcomes", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        hp = (100 if program == "kill" else 150) + (outcome == "threshold")
        target.receive_damage(target.get_normal_hp() - hp, DamageType.PSYCHIC, caster.uuid)
        target.health.add_temporary_hit_points(20, target.uuid)
        if outcome == "immune":
            target.add_condition_immunity("Stunned", immunity_name="Creature immunity")
        if outcome == "ward":
            target.add_condition(DeathWardEffect(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
        elif outcome == "prone":
            target.add_condition(Prone(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Power Word initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        choices = [(action, selection) for action in get_available_actions(caster).all_actions
            if action.behavior_id == "spell.power_word_" + program for selection in action.valid_targets
            if selection.target_uuid == target.uuid]
        assert choices
        with fixed_dice_faces(10):
            result = execute_available_action(caster, *choices[0])
        assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
        if program == "stun" and outcome not in ("threshold", "immune"):
            with fixed_dice_faces(1):
                target.on_turn_end()
            assert "Stunned" in target.active_conditions
            with fixed_dice_faces(20):
                target.on_turn_end()
            assert "Stunned" not in target.active_conditions
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
