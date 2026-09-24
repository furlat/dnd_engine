"""Registered support actions and their real condition lifecycles, saved once."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Poisoned
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_conditions import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.types.abilities import AbilityName
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import DeathWard, FreedomOfMovement, ProtectionFromPoison, RemoveCurse, Stoneskin
from dnd.spells.necromancy import AbilityCurseEffect
from dnd.spells.transmutation import EnhanceAbility, Regenerate
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


SupportConditionProgram = Literal["death_ward", "stoneskin", "protection_from_poison",
    "enhance_ability", "regenerate", "remove_curse", "freedom_of_movement"]
SupportConditionMode = Literal["lifecycle", "lethal", "instant", "clean", "full_hp"]
SPELLS = {"death_ward": DeathWard, "stoneskin": Stoneskin, "protection_from_poison": ProtectionFromPoison,
    "enhance_ability": EnhanceAbility, "regenerate": Regenerate, "remove_curse": RemoveCurse,
    "freedom_of_movement": FreedomOfMovement}
CONDITIONS = {"death_ward": "Death Ward", "stoneskin": "Stoneskin",
    "protection_from_poison": "Protection from Poison", "enhance_ability": "Enhance Ability",
    "regenerate": "Regenerating", "freedom_of_movement": "Freedom of Movement"}


def support_condition_history(*, program: SupportConditionProgram, self_target: bool = False,
                              ability: AbilityName = "strength",
                              mode: SupportConditionMode = "lifecycle") -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("caster", (3, 6)), ("recipient", (4, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2: 3, 3: 3, 4: 3, 7: 3}),
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
                if program == "enhance_ability":
                    actor.register_action(EnhanceAbility(source_entity_uuid=actor.uuid,
                        enhance_ability_type=ability, caster_level=17, template=True))
                else:
                    register_spell(actor, SPELLS[program], caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster = actors["caster"]
        recipient = caster if self_target else actors["recipient"]
        encounter = Encounter(name="Support condition lifecycles", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, *, target: Entity | None = None,
                    destination: tuple[int, int] | None = None) -> None:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            choices = [(action, option) for action in get_available_actions(actor).all_actions
                       if action.behavior_id == behavior for option in action.valid_targets
                       if (target is None or option.target_uuid == target.uuid)
                       and (destination is None or option.position == destination)]
            assert choices, (program, ability, behavior, destination)
            with fixed_dice_faces(*([4] * 30)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        if program == "regenerate" and mode != "full_hp":
            recipient.receive_damage(60, DamageType.PSYCHIC, caster.uuid)
        if program == "death_ward" and mode == "lethal":
            recipient.receive_damage(recipient.get_normal_hp() - 10, DamageType.PSYCHIC, caster.uuid)
        if program == "protection_from_poison" and mode != "clean":
            recipient.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
        if program == "remove_curse" and mode != "clean":
            recipient.add_condition(AbilityCurseEffect(source_entity_uuid=caster.uuid,
                target_entity_uuid=recipient.uuid, cursed_ability="strength"))
            assert any(ConditionTag.CURSE in condition.tags for condition in recipient.active_conditions.values())

        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Support initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, "spell." + program, target=recipient)

        if program == "remove_curse":
            assert not any(ConditionTag.CURSE in condition.tags for condition in recipient.active_conditions.values())
        else:
            assert CONDITIONS[program] in recipient.active_conditions
            # Both camera basis and target attachment must remain correct while
            # the actual buff owner walks, including self-cast variants.
            perform(recipient, "action.move", destination=(recipient.position[0], 8))
            if program in ("stoneskin", "enhance_ability", "protection_from_poison", "freedom_of_movement"):
                # Walk around a corner and return on a fresh turn: the camera
                # banks remain world-oriented while the wearer changes facing.
                origin_x = recipient.position[0]
                perform(recipient, "action.move", destination=(origin_x + 3, 8))
                encounter.next_turn()
                perform(recipient, "action.move", destination=(origin_x, 6))
            if program == "death_ward" and mode == "lethal":
                recipient.receive_damage(2, DamageType.FORCE, caster.uuid)
                assert "Death Ward" in recipient.active_conditions
                recipient.receive_damage(100, DamageType.FORCE, caster.uuid)
                assert recipient.get_normal_hp() == 1 and "Death Ward" not in recipient.active_conditions
                recipient.receive_damage(2, DamageType.FORCE, caster.uuid)
                assert recipient.get_normal_hp() <= 0
            elif program == "death_ward" and mode == "instant":
                event = recipient.receive_instant_death(caster.uuid, source_description="Native instant death")
                assert event.canceled and "Death Ward" not in recipient.active_conditions
            elif program == "regenerate":
                # Turn advancement invokes the condition's real healing handler;
                # no preview clock or authored synthetic HealEvent is involved.
                for _ in range(22):
                    if "Regenerating" not in recipient.active_conditions:
                        break
                    encounter.next_turn()
                assert "Regenerating" not in recipient.active_conditions
            else:
                if program == "protection_from_poison":
                    assert "Poisoned" not in recipient.active_conditions
                # Concentration and direct native removal exercise distinct
                # ordinary-removal paths without pretending time has expired.
                if program in ("stoneskin", "enhance_ability"):
                    caster.remove_condition("Concentrating")
                else:
                    recipient.remove_condition(CONDITIONS[program])
                assert CONDITIONS[program] not in recipient.active_conditions

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
