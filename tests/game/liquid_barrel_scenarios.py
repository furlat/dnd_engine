"""Break real barrels, then cross their native contents from two viewpoints."""

import random
from typing import Literal

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door, build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import attack_object, review_actor, take_turn, walk


Liquid = Literal["oil", "water", "grease", "poison", "blood", "dread_blood"]


def perform(actor: Entity, behavior: str, *, destination: tuple[int, int] | None = None,
            face: int = 20) -> Event:
    actor.update_entity_senses()
    choices = [(row, target) for row in get_available_actions(actor).all_actions
        if row.behavior_id == behavior for target in row.valid_targets
        if destination is None or target.position == destination]
    assert choices, f"No discovered {behavior} for {actor.name}: {destination}"
    row, target = choices[0]
    with fixed_dice_faces(face):
        result = execute_available_action(actor, row, target)
    assert result is not None and not result.canceled, result
    return result


def liquid_barrel_history(*, liquid: Liquid, saved: bool = True,
                          jump: bool = False, late_snapshot: bool = False,
                          layout: Literal["open", "door-closed", "door-open"] = "open",
                          landing: Literal["edge", "center"] = "edge") -> CapturedHistory:
    """Fixed dice select outcomes; state changes come only from native actions."""
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        if layout != "open":
            for y in (3, 5):
                build_directional_wall().place_on_grid((5, y), boundary_direction=CardinalDirection.EAST)
            build_directional_door(is_open=layout == "door-open").place_on_grid(
                (5, 4), boundary_direction=CardinalDirection.EAST)
        actors = {role: review_actor(game, role.title(), position, strength=18)
                  for role, position in (("traveler", (4, 4)),
                                        ("witness", (8, 6) if layout == "open" else (4, 7)))}
        traveler = actors["traveler"]
        barrel = build_authored_item(f"environment.blocker.{liquid}_barrel", traveler.uuid)
        barrel.place_on_grid((5, 4))
        encounter = Encounter(name="Barrels and their contents", source_entity_uuid=traveler.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, traveler)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Liquid barrel and witnesses", start_cursor=0, end_cursor=baseline,
            observer_uuid=traveler.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        for damage in (4, 8):
            take_turn(encounter, traveler, fresh=True)
            attack_object(traveler, barrel, damage, additional_dice=(20,))
        assert barrel.integrity is ItemIntegrity.DESTROYED and barrel.get_position() == (5, 4)
        # The attacker is adjacent to the barrel and therefore inside its new
        # footprint. Walk out before testing boundary entry and aerial bypass.
        walk(traveler, (3, 4))
        take_turn(encounter, traveler, fresh=True)
        hp = traveler.get_hp()
        contact_face = 2 if liquid == "poison" else (20 if saved else 1)
        if jump:
            perform(traveler, "action.jump", destination=(7, 4))
            assert traveler.position == (7, 4) and traveler.get_hp() == hp
            assert not {"Wet", "Prone", "Frightened"}.intersection(traveler.active_conditions)
            take_turn(encounter, traveler, fresh=True)
            if liquid == "grease" and not saved:
                for position in ((8, 4), (8, 3), (7, 4)):
                    walk(traveler, position)
            perform(traveler, "action.jump", destination=(5, 4) if landing == "center" else (6, 4),
                    face=contact_face)
        else:
            if liquid == "grease" and not saved:
                for position in ((2, 4), (2, 3), (3, 4)):
                    walk(traveler, position)
            walk(traveler, (4, 4), accepted=saved or liquid != "dread_blood",
                 dice=(contact_face,))
        outside, inside = ((7, 4), (6, 4)) if jump else ((3, 4), (4, 4))
        if liquid == "dread_blood" and not saved:
            if landing == "center":
                assert traveler.position == inside and "Frightened" in traveler.active_conditions
                walk(traveler, outside)
            assert traveler.position == outside
            assert "Frightened" not in traveler.active_conditions
        else:
            assert traveler.position == inside
            if liquid == "grease" and not saved:
                assert "Prone" in traveler.active_conditions
                # The existing turn-start handler pays to stand up. Spending
                # movement before entry prevents the own-turn immediate stand.
                take_turn(encounter, traveler, fresh=True)
                assert "Prone" not in traveler.active_conditions
            if liquid == "water":
                assert "Wet" in traveler.active_conditions
            if liquid == "poison":
                assert traveler.get_hp() < hp
            # Leave before renewing the turn; Grease also saves at turn end.
            walk(traveler, outside, dice=(20,))
            assert "Wet" not in traveler.active_conditions
            take_turn(encounter, traveler, fresh=True)
            walk(traveler, inside, dice=(2 if liquid == "poison" else 20,))
            walk(traveler, outside, dice=(20,))
        if late_snapshot:
            baseline = EventQueue.event_cursor()
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["traveler"]
        if late_snapshot:
            before, _ = reduce_interval(None, primary.initialization)
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
