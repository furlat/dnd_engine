"""Discovered support actions and real condition lifecycles, recorded once."""

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
from dnd.core.base_block import LightLevel
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import Resistance, ShieldOfFaith
from dnd.spells.divination import Guidance
from dnd.spells.evocation import CureWounds, HealingWord, Light, PrayerOfHealing
from dnd.spells.infernal import Thaumaturgy
from dnd.types.senses import SenseMode, SensesType
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


SupportProgram = Literal["cure_wounds", "healing_word", "prayer_of_healing", "guidance",
                         "resistance", "shield_of_faith", "light", "thaumaturgy", "stacked"]
SPELLS = {"cure_wounds": CureWounds, "healing_word": HealingWord, "prayer_of_healing": PrayerOfHealing,
          "guidance": Guidance, "resistance": Resistance, "shield_of_faith": ShieldOfFaith,
          "light": Light, "thaumaturgy": Thaumaturgy}
CONDITIONS = {"guidance": "Guidance", "resistance": "Resistance", "shield_of_faith": "Shield of Faith",
              "light": "Light"}


def support_history(*, program: SupportProgram = "cure_wounds", diagonal: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    if program == "light":
        for x in range(15):
            for y in range(15):
                get_map().set_tile_base_light((x, y), LightLevel.DARKNESS)
    game = Game()
    try:
        positions = {"caster": (3, 6), "recipient": (4, 7 if diagonal else 6)}
        if program == "prayer_of_healing":
            positions.update(second=(5, 6), unselected=(5, 8))
        elif program == "stacked":
            positions = {"caster": (5, 6), "recipient": (6, 6), "resistance": (5, 5),
                         "shield": (6, 5), "light": (7, 6)}
        grants = ({"caster": "guidance", "resistance": "resistance", "shield": "shield_of_faith",
                   "light": "light", "recipient": "guidance"} if program == "stacked" else {"caster": program})
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={1: 2, 2: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=6, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            if program == "light":
                actor.senses.add_sense_mode_source(actor.uuid, SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
            setup_standard_actions(actor)
            if role in grants:
                register_spell(actor, SPELLS[grants[role]], caster_level=5)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Support spell delivery", source_entity_uuid=caster.uuid)
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
            assert choices, (actor.name, behavior, target.name if target else destination)
            with fixed_dice_faces(*([4] * 24)):
                result = execute_available_action(actor, *choices[0],
                    extra_target_uuids=[str(row.uuid) for row in additional])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        healing = program in ("cure_wounds", "healing_word", "prayer_of_healing")
        if healing:
            for role, actor in actors.items():
                if role != "caster":
                    actor.receive_damage(20, DamageType.SLASHING, caster.uuid)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Support initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        if program == "stacked":
            for role, spell in grants.items():
                perform(actors[role], "spell." + spell, target=caster if role == "recipient" else recipient)
            assert all(name in recipient.active_conditions for name in CONDITIONS.values())
            perform(recipient, "action.move", destination=(6, 8))
            for role, spell in grants.items():
                perform(actors[role], "action.drop_concentration")
                assert CONDITIONS[spell] not in (caster if role == "recipient" else recipient).active_conditions
        else:
            perform(caster, "spell." + program, target=None if program == "thaumaturgy" else recipient,
                additional=(actors["second"],) if program == "prayer_of_healing" else ())
            if healing:
                assert recipient.get_hp() == 40 + (12 if program == "prayer_of_healing" else 8)
                if program == "prayer_of_healing":
                    assert actors["second"].get_hp() == 52 and actors["unselected"].get_hp() == 40
            elif program in CONDITIONS:
                assert CONDITIONS[program] in recipient.active_conditions
                perform(recipient, "action.move", destination=(6, 7))
                perform(caster, "action.drop_concentration")
                assert CONDITIONS[program] not in recipient.active_conditions
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
