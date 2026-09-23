"""Six support spells exercised through native discovery, then saved for replay."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Deafened, Poisoned
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import Aid, GreaterRestoration, LesserRestoration
from dnd.spells.evocation import HealSpell, MassCureWounds, MassHeal
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


HealingProgram = Literal["aid", "lesser_restoration", "greater_restoration", "heal", "mass_cure_wounds", "mass_heal"]
SPELLS = {"aid": Aid, "lesser_restoration": LesserRestoration, "greater_restoration": GreaterRestoration,
          "heal": HealSpell, "mass_cure_wounds": MassCureWounds, "mass_heal": MassHeal}


def healing_batch_history(*, program: HealingProgram, self_target: bool = False,
                          clean_target: bool = False, repeat_aid: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        positions = {"caster": (3, 6), "recipient": (4, 6)}
        multi = program in ("aid", "mass_cure_wounds", "mass_heal")
        if multi:
            positions.update(second=(6, 5), third=(6, 7), bystander=(5, 8))
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position,
                # Mass Cure's existing resolver selects eligible allies in its
                # area; other multi-entity spells use an explicit selected list.
                faction="neutral" if role == "bystander" and program == "mass_cure_wounds" else "heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2: 2, 5: 2, 6: 2, 9: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, SPELLS[program], caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster = actors["caster"]
        recipient = caster if self_target else actors["recipient"]
        encounter = Encounter(name="Healing and restoration", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, *, target: Entity | None = None,
                    destination: tuple[int, int] | None = None, additional: tuple[Entity, ...] = ()) -> None:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            choices = [(action, option) for action in get_available_actions(actor).all_actions
                       if action.behavior_id == behavior for option in action.valid_targets
                       if (target is None or option.target_uuid == target.uuid)
                       and (destination is None or option.position == destination)]
            assert choices, (program, behavior, target.name if target else destination)
            with fixed_dice_faces(*([4] * 30)):
                result = execute_available_action(actor, *choices[0],
                    extra_target_uuids=[str(row.uuid) for row in additional])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        for role, actor in actors.items():
            actor.receive_damage(8 if role == "second" else 35, DamageType.PSYCHIC, caster.uuid)
        if not clean_target and program in ("lesser_restoration", "greater_restoration"):
            recipient.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
        elif not clean_target and program in ("heal", "mass_heal"):
            recipient.add_condition(Deafened(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Healing initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        initial_hp = {role: (actor.get_normal_hp(), actor.get_max_hp()) for role, actor in actors.items()}
        perform(caster, "spell." + program,
            target=None if program == "mass_cure_wounds" else recipient,
            destination=(5, 6) if program == "mass_cure_wounds" else None,
            additional=(actors["second"], actors["third"]) if program in ("aid", "mass_heal") else ())

        if program == "aid":
            if repeat_aid:
                encounter.next_turn()
                perform(caster, "spell.aid", target=recipient, additional=(actors["second"], actors["third"]))
            for role in ("recipient", "second", "third"):
                assert (actors[role].get_normal_hp(), actors[role].get_max_hp()) == tuple(v + 5 for v in initial_hp[role])
            assert "Aid" not in actors["bystander"].active_conditions
            perform(recipient, "action.move", destination=(4, 9))
            perform(actors["second"], "action.move", destination=(8, 5))
            # Explicit native removal: Aid does not use concentration. This
            # lifecycle fixture does not pretend a turn advance expires it.
            for role in ("recipient", "second", "third"):
                actors[role].remove_condition("Aid")
                assert (actors[role].get_normal_hp(), actors[role].get_max_hp()) == initial_hp[role]
        elif program in ("heal", "mass_heal"):
            assert recipient.get_normal_hp() == 120 and "Deafened" not in recipient.active_conditions
            if multi:
                assert actors["second"].get_normal_hp() == actors["third"].get_normal_hp() == 120
        elif program == "mass_cure_wounds":
            assert recipient.get_normal_hp() == 101 and actors["second"].get_normal_hp() == 120
        else:
            assert "Poisoned" not in recipient.active_conditions
            assert recipient.get_normal_hp() == initial_hp["caster" if self_target else "recipient"][0]
        if multi:
            assert actors["bystander"].get_normal_hp() == initial_hp["bystander"][0]

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
