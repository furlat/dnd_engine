"""Existing condition mechanics applied and removed through native events."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Incapacitated, Paralyzed, Petrified, Prone, Restrained, Stunned, NoReactions, Unconscious
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.necromancy import SickenedCondition, NoHealing
from dnd.spells.evocation import GuidingBoltMarked
from dnd.monsters.skeleton_abilities import Marked
from dnd.monsters.traits import LifeDrainReduction
from dnd.extensions.field_focus import FieldFocus
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


CONDITIONS = {"unconscious": Unconscious,"petrified": Petrified, "restrained": Restrained, "incapacitated": Incapacitated, "stunned": Stunned, "sickened": SickenedCondition, "marked": Marked, "field_focus": FieldFocus, "life_drain": LifeDrainReduction, "no_reactions": NoReactions, "guiding_mark": GuidingBoltMarked, "no_healing": NoHealing}


def shared_condition_history(*, program: Literal["petrified", "restrained", "incapacitated", "stunned", "sickened", "marked", "field_focus", "life_drain", "no_reactions", "guiding_mark", "no_healing", "multiple_marks", "unconscious"],
                             prior: Literal["prone", "paralyzed"] | None = None) -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Recipient", config=EntityConfig(position=(6, 6), faction="heroes",
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=10, mode="maximums")]),
            appearance=AppearanceConfig(body_category="NakedBody", has_beard=False, head_category="Head22")))
        actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
            (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
        setup_standard_actions(actor)
        actor.compose_entity()
        game.deploy_entity(actor, (6, 6))
        encounter = Encounter(name="Shared condition lifecycle", source_entity_uuid=actor.uuid)
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        encounter.start_encounter()
        encounter.start_turn()
        previous = None
        if prior == "prone":
            previous = Prone(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
            previous.suppress_immediate_stand_for_application()
        elif prior == "paralyzed":
            previous = Paralyzed(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
        if previous is not None:
            applied_prior = actor.add_condition(previous)
            assert applied_prior is not None and not applied_prior.canceled
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Shared condition initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=actor.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        if program == "multiple_marks":
            active = [NoReactions(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid),
                      Marked(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid),
                      LifeDrainReduction(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, amount=5)]
            for mark in active:
                event = actor.add_condition(mark)
                assert event is not None and not event.canceled
            for mark in active:
                assert actor.remove_condition_by_uuid(mark.uuid)
            captured = capture_history(before, (), observers=(ObserverCapture("recipient", actor.uuid, baseline),))
            primary = captured.views["recipient"]
            return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
        condition = (LifeDrainReduction(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, amount=5)
                     if program == "life_drain" else
                     GuidingBoltMarked(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, caster_uuid=actor.uuid)
                     if program == "guiding_mark" else
                     CONDITIONS[program](source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
        if program == "unconscious":
            condition.duration = Duration(duration=1, duration_type=DurationType.ROUNDS,
                source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
        applied = actor.add_condition(condition)
        assert applied is not None and not applied.canceled
        if previous is not None and program != "unconscious":
            actor.remove_condition_by_uuid(previous.uuid)
        if program in ("petrified", "restrained", "incapacitated", "stunned"):
            actor.on_turn_end()
            actor.on_turn_start()
        if program == "unconscious":
            encounter.next_turn()
            assert "Unconscious" not in actor.active_conditions
        else:
            assert actor.remove_condition_by_uuid(condition.uuid)
        captured = capture_history(before, (), observers=(ObserverCapture("recipient", actor.uuid, baseline),))
        primary = captured.views["recipient"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
