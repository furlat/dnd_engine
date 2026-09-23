"""Native area casts with saves, displacement and concentration cleanup."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import BurningHands, GustOfWind, Thunderwave
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


AreaProgram = Literal["burning_hands", "thunderwave", "gust_of_wind"]


def area_spell_history(*, program: AreaProgram = "burning_hands",
                       diagonal: bool = False, blocked: bool = False) -> CapturedHistory:
    """Use real discovered actions and two observers; no outcome-state edits.

    One recipient has a weak save and the other a strong save. A solid boundary
    optionally stops the failed-save recipient's push after one admitted step.
    Gust remains present through the next turn cycle, then its caster uses the
    ordinary Drop Concentration action.
    """
    if blocked and (diagonal or program == "burning_hands"):
        raise ValueError("The authored push-stop fixture is axial Thunderwave/Gust")
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        caster_position = (3, 5)
        if diagonal and program != "thunderwave":
            caster_position = (3, 3)
            positions = {"caster": caster_position, "target": (4, 4), "saved": (5, 5), "outside": (3, 7)}
            if program == "gust_of_wind":
                positions["saved"] = (4, 6)
            destination = (4, 4)
        else:
            positions = {"caster": caster_position, "target": (4, 5), "saved": (5, 4), "outside": (3, 8)}
            if program == "burning_hands":
                positions["saved"] = (5, 5)
            if diagonal and program == "thunderwave":
                positions["target"] = (4, 6)
            destination = (4, 6) if diagonal else (4, 5)
        if blocked:
            build_directional_wall().place_on_grid((5, 5), boundary_direction=CardinalDirection.EAST)
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            save_score = 20 if role == "saved" else 8
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(
                    intelligence=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=save_score),
                    dexterity=AbilityConfig(ability_score=save_score),
                    constitution=AbilityConfig(ability_score=save_score),
                ),
                action_economy=ActionEconomyConfig(spell_slots={1: 1, 2: 1}),
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
                register_spell(actor, {"burning_hands": BurningHands, "thunderwave": Thunderwave,
                                       "gust_of_wind": GustOfWind}[program], caster_level=3)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster = actors["caster"]
        encounter = Encounter(name="Authored area delivery", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Area initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        behavior = "spell." + program
        available = get_available_actions(caster)
        def desired_position(position: tuple[int, int] | None) -> bool:
            if position is None:
                return False
            if program == "thunderwave":
                # Discovery collapses equivalent cube directions. Select its
                # existing eastward cube; the target can still be pushed diagonally.
                dx, dy = position[0] - caster_position[0], position[1] - caster_position[1]
                return dx > 0 and abs(dx) >= abs(dy)
            return position == destination
        selected = [(action, target) for action in available.all_actions
                    if action.behavior_id == behavior
                    for target in action.valid_targets if desired_position(target.position)]
        assert selected, (behavior, destination, [(row.behavior_id, [target.position for target in row.valid_targets])
                          for row in available.all_actions if row.behavior_id == behavior])
        action, target = selected[0]
        damage_dice = {"burning_hands": 3, "thunderwave": 2, "gust_of_wind": 0}[program]
        packet = (10, *((4,) * damage_dice))
        with fixed_dice_faces(*(packet * 4)):
            cast = execute_available_action(caster, action, target)
        assert isinstance(cast, SpellEvent) and not cast.canceled and cast.phase is EventPhase.COMPLETION
        assert cast.area_geometry is not None and cast.resolved_area_positions is not None
        assert actors["outside"].get_hp() == before.actors[actors["outside"].uuid].normal_hp
        if program == "gust_of_wind":
            assert "Concentrating" in caster.active_conditions
            with fixed_dice_faces(*([10] * 30)):
                encounter.next_turn()
                while encounter.get_current_entity() is not caster:
                    encounter.next_turn()
            choices = [(row, choice) for row in get_available_actions(caster).all_actions
                       if row.behavior_id == "action.drop_concentration" for choice in row.valid_targets]
            assert choices
            end = execute_available_action(caster, *choices[0])
            assert end is not None and not end.canceled and "Concentrating" not in caster.active_conditions
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "target")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
