"""Real native control actions and condition lifetimes for saved review inputs."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import Move, SpellAction, SpellEvent
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
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
from dnd.spells.enchantment import CharmPerson, Command, Sleep
from dnd.spells.evocation import FireBolt
from dnd.spells.illusion import ColorSpray, Silence
from dnd.spells.necromancy import BlindnessDeafness
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


ControlProgram = Literal[
    "charm", "blindness", "deafness", "grovel", "halt", "flee", "color-spray",
    "silence", "blindness-overlap", "deafness-overlap", "sleep-long",
]


def control_spell_history(
    *, program: ControlProgram = "charm", saved: bool = False,
    remove_first: Literal["independent", "area"] = "independent",
    repeat_source: bool = False,
) -> CapturedHistory:
    """Compose legal native casts, movement, turns and removals, then freeze both views.

    Dice determine outcomes; no condition, HP, position or event record is edited
    after the action. Direct native spell actions retain their normal costs and
    targeting validation. Independent condition removal uses the native lifecycle.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        positions = {"caster": (3, 6)}
        if program.endswith("overlap") or repeat_source:
            positions["other"] = (3, 7)
        positions["recipient"] = (4, 6)
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="enemies" if role == "recipient" else "heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={1: 3, 2: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=1 if role == "recipient" else 8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role != "recipient":
                for spell_type in (CharmPerson, Command, Sleep, FireBolt, ColorSpray, Silence, BlindnessDeafness):
                    register_spell(actor, spell_type)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Control condition lifetimes", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity) -> None:
            with fixed_dice_faces(*([1] * 40)):
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()

        def cast(actor: Entity, spell: SpellAction, *, faces: tuple[int, ...] | None = None) -> SpellEvent:
            turn(actor)
            template = next(action for action in actor.registered_actions if type(action) is type(spell))
            instance = template.instantiate(target_entity_uuid=spell.target_entity_uuid,
                end_position=spell.end_position, cast_at_level=spell.cast_at_level)
            if isinstance(instance, BlindnessDeafness) and isinstance(spell, BlindnessDeafness):
                instance.effect_type = spell.effect_type
            if isinstance(instance, Command) and isinstance(spell, Command):
                instance.command_word = spell.command_word
            with fixed_dice_faces(*(faces or ((20,) * 24 if saved else (1,) * 24))):
                result = instance.apply()
            assert isinstance(result, SpellEvent) and not result.canceled, result
            assert result.phase is EventPhase.COMPLETION
            return result

        def move(actor: Entity, destination: tuple[int, int]) -> None:
            turn(actor)
            template = next(action for action in actor.registered_actions if isinstance(action, Move))
            result = template.instantiate(end_position=destination).apply()
            assert result is not None and not result.canceled, result
            assert actor.position == destination

        turn(caster)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Control initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        if program == "charm":
            cast(caster, CharmPerson(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid,
                                    cast_at_level=1))
            if not saved:
                assert "Charmed" in recipient.active_conditions
                if repeat_source:
                    other = actors["other"]
                    cast(other, CharmPerson(source_entity_uuid=other.uuid, target_entity_uuid=recipient.uuid,
                                            cast_at_level=1))
                    assert recipient.active_conditions["Charmed"].source_entity_uuid == other.uuid
                move(recipient, (5, 6))
                assert recipient.remove_condition("Charmed")
        elif program in ("blindness", "deafness"):
            mode = "blinded" if program == "blindness" else "deafened"
            cast(caster, BlindnessDeafness(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid,
                                          effect_type=mode, cast_at_level=2))
            if not saved:
                assert mode.title() in recipient.active_conditions
                if program == "blindness":
                    # Native path discovery requires visible cells; let the caster
                    # move while the blinded recipient retains the effect.
                    move(caster, (3, 5))
                    turn(recipient)
                else:
                    move(recipient, (5, 6))
                # A successful real repeat save ends the effect at this target's turn end.
                with fixed_dice_faces(20):
                    encounter.next_turn()
                assert mode.title() not in recipient.active_conditions
        elif program in ("grovel", "halt", "flee"):
            start_position = recipient.position
            cast(caster, Command(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid,
                                 command_word=program, cast_at_level=1))
            if not saved:
                condition = f"Command: {program.title()}"
                assert condition in recipient.active_conditions and "Prone" not in recipient.active_conditions
                turn(recipient)
                assert recipient.action_economy.actions.normalized_score == 0
                assert recipient.action_economy.reactions.normalized_score == 1
                assert ("Prone" in recipient.active_conditions) is (program == "grovel")
                assert (recipient.position != start_position) is (program == "flee")
                encounter.next_turn()
                assert condition not in recipient.active_conditions
                if program == "grovel":
                    assert "Prone" in recipient.active_conditions
        elif program in ("color-spray", "blindness-overlap"):
            cast(caster, ColorSpray(source_entity_uuid=caster.uuid, end_position=(8, 6), cast_at_level=1),
                 faces=(8,) * 6)
            assert "Color Spray" in recipient.active_conditions
            if program == "blindness-overlap":
                other = actors["other"]
                cast(other, BlindnessDeafness(source_entity_uuid=other.uuid,
                    target_entity_uuid=recipient.uuid, effect_type="blinded", cast_at_level=2))
                first = "Blindness/Deafness" if remove_first == "independent" else "Color Spray"
                assert recipient.remove_condition(first)
                assert not recipient.can_see_visual_effects()
                assert recipient.remove_condition("Color Spray" if first == "Blindness/Deafness" else "Blindness/Deafness")
                assert recipient.can_see_visual_effects()
            else:
                move(recipient, (5, 6))
                turn(caster)
                encounter.next_turn()
                assert "Color Spray" not in recipient.active_conditions
        elif program in ("silence", "deafness-overlap"):
            # The target starts just outside; both casters remain outside sound denial.
            cast(caster, Silence(source_entity_uuid=caster.uuid, end_position=(9, 6), cast_at_level=2))
            assert "Deafened" not in recipient.active_conditions
            move(recipient, (5, 6))
            assert "Deafened" in recipient.active_conditions
            if program == "deafness-overlap":
                other = actors["other"]
                cast(other, BlindnessDeafness(source_entity_uuid=other.uuid,
                    target_entity_uuid=recipient.uuid, effect_type="deafened", cast_at_level=2))
                if remove_first == "independent":
                    assert recipient.remove_condition("Blindness/Deafness")
                    assert "Deafened" in recipient.active_conditions
                    move(recipient, (4, 6))
                else:
                    move(recipient, (4, 6))
                    assert "Deafened" in recipient.active_conditions
                    assert recipient.remove_condition("Blindness/Deafness")
            else:
                move(recipient, (4, 6))
                assert "Deafened" not in recipient.active_conditions
                move(recipient, (5, 6))
            assert caster.remove_condition("Concentrating")
            assert "Deafened" not in recipient.active_conditions
        else:
            cast(caster, Sleep(source_entity_uuid=caster.uuid, end_position=recipient.position, cast_at_level=1),
                 faces=(8,) * 5)
            assert "Sleep" in recipient.active_conditions
            # Sustained sleep spans actual travel and another caster turn before damage.
            move(caster, (3, 1))
            move(caster, (2, 1))
            turn(recipient)
            turn(caster)
            move(caster, (2, 6))
            cast(caster, FireBolt(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid),
                 faces=(15, 2))
            assert "Sleep" not in recipient.active_conditions and recipient.get_hp() == 8
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
