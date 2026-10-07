"""Native divine support selections and outcomes, retained for paired replay."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import BeaconOfHope
from dnd.spells.conjuration import Daylight
from dnd.spells.evocation import MassHealingWord, DivineWord, FlameStrike
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


DivineProgram = Literal["beacon_of_hope", "daylight", "mass_healing_word", "divine_word", "flame_strike"]
SPELLS = {"beacon_of_hope": BeaconOfHope, "daylight": Daylight,
          "mass_healing_word": MassHealingWord, "divine_word": DivineWord, "flame_strike": FlameStrike}


def divine_history(*, program: DivineProgram, multiple_targets: bool = True) -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (("caster", (1, 6) if program == "flame_strike" else (3, 6)), ("recipient", (5, 6)), ("second", (6, 5)), ("bystander", (6, 8))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="monsters" if program == "divine_word" and role != "caster" else "heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={3: 3, 5: 3, 7: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, SPELLS[program], caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Divine native outcomes", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, target: Entity | None = None,
                    destination: tuple[int, int] | None = None, additional: tuple[Entity, ...] = ()) -> None:
            while encounter.get_current_entity() is not actor:
                with fixed_dice_faces(*([4] * 30)):
                    encounter.next_turn()
            choices = [(action, selection) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior for selection in action.valid_targets
                if (target is None or selection.target_uuid == target.uuid)
                and (destination is None or selection.position == destination)]
            assert choices, (behavior, destination)
            with fixed_dice_faces(*([4] * 30)):
                result = execute_available_action(actor, *choices[0], extra_target_uuids=[str(item.uuid) for item in additional])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        if program in ("mass_healing_word", "divine_word"):
            for role in ("recipient", "second", "bystander"):
                actors[role].receive_damage(85 if program == "divine_word" else 35,
                    DamageType.PSYCHIC, caster.uuid)
        initial_hp = {role: actor.get_normal_hp() for role, actor in actors.items()}
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Divine initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, "spell." + program,
            target=None if program in ("daylight", "flame_strike") else recipient,
            destination=(5, 7) if program == "daylight" else (5, 6) if program == "flame_strike" else None,
            additional=() if program in ("daylight", "flame_strike") or not multiple_targets else (actors["second"],))
        if program == "beacon_of_hope":
            assert "Beacon of Hope" in recipient.active_conditions
            assert "Beacon of Hope" not in actors["bystander"].active_conditions
            perform(recipient, "action.move", destination=(5, 8))
            caster.remove_condition("Concentrating")
            assert "Beacon of Hope" not in recipient.active_conditions
        elif program == "daylight":
            caster.remove_condition("Concentrating")
        elif program == "mass_healing_word":
            assert recipient.get_normal_hp() > initial_hp["recipient"]
            if multiple_targets:
                assert actors["second"].get_normal_hp() > initial_hp["second"]
        elif program == "flame_strike":
            assert recipient.get_normal_hp() < initial_hp["recipient"]
            assert actors["second"].get_normal_hp() < initial_hp["second"]
            assert caster.get_normal_hp() == initial_hp["caster"]
        else:
            assert "Blinded" in recipient.active_conditions
            assert "Deafened" in recipient.active_conditions
        assert actors["bystander"].get_normal_hp() == initial_hp["bystander"]
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
