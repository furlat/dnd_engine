"""Real discovered direct and touch cantrips, captured for both participants."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import PoisonSpray
from dnd.spells.evocation import SacredFlame, ShockingGrasp
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


CantripProgram = Literal["sacred", "shocking", "poison"]
CantripOutcome = Literal["hit", "saved", "miss"]
CantripLayout = Literal["adjacent-axis", "adjacent-diagonal", "range-axis", "range-diagonal"]


def cantrip_history(*, program: CantripProgram = "sacred", outcome: CantripOutcome = "hit",
                    layout: CantripLayout = "adjacent-axis") -> CapturedHistory:
    """Fixture positions and dice exercise native discovery, costs and outcomes.

    Shocking Grasp's five-foot maximum is adjacent. The other maximum-range
    placements use the engine's existing floored Euclidean distance rule.
    Both participants receive their own real initialization and causal lineages.
    """
    if (program == "shocking" and outcome == "saved") or (program != "shocking" and outcome == "miss"):
        raise ValueError("Shocking Grasp attacks; Sacred Flame and Poison Spray require saves")
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        diagonal = layout.endswith("diagonal")
        maximum = layout.startswith("range")
        distance = {"sacred": 9 if diagonal else 12, "poison": 2, "shocking": 1}[program] if maximum else 1
        caster_position = (2, 2) if diagonal and maximum and program == "sacred" else (2, 7)
        target_position = (caster_position[0] + distance, caster_position[1] + (distance if diagonal else 0))
        actors: dict[str, Entity] = {}
        for role, position in (("caster", caster_position), ("perceiver", target_position)):
            actor = Entity.create(uuid4(), "Caster" if role == "caster" else "Target", config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    dexterity=AbilityConfig(ability_score=10), constitution=AbilityConfig(ability_score=10)),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=6, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, {"sacred": SacredFlame, "shocking": ShockingGrasp,
                                       "poison": PoisonSpray}[program], caster_level=1)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["perceiver"]
        encounter = Encounter(name="Direct and touch cantrip delivery", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Cantrip initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        behavior = {"sacred": "spell.sacred_flame", "shocking": "spell.shocking_grasp",
                    "poison": "spell.poison_spray"}[program]
        choices = [(action, target) for action in get_available_actions(caster).all_actions
                   if action.behavior_id == behavior
                   for target in action.valid_targets if target.target_uuid == recipient.uuid]
        assert choices, (behavior, layout, recipient.position)
        expected_range = {"sacred": 60, "shocking": 5, "poison": 10}[program]
        if maximum:
            assert caster.senses.get_feet_distance(recipient.position) == expected_range
        start_hp = recipient.get_hp()
        dice = (15, 4) if program == "shocking" else (1, 4)
        if outcome != "hit":
            dice = (1,) if outcome == "miss" else (20,)
        with fixed_dice_faces(*dice):
            result = execute_available_action(caster, *choices[0])
        assert isinstance(result, SpellEvent) and not result.canceled and result.phase is EventPhase.COMPLETION
        assert recipient.get_hp() == start_hp - (4 if outcome == "hit" else 0)
        assert ("No Reactions" in recipient.active_conditions) is (program == "shocking" and outcome == "hit")
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
