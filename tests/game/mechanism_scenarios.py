"""Native pressure/control/trap narratives, recorded once from both participants."""

from typing import Literal
from uuid import uuid4

from dnd.actions import Jump, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door, build_standing_torch
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.mechanisms import (
    AreaGeometry, LaneGeometry, TrapSave, materialize_finite_trap,
    DART_LAUNCHER_CONTENT_REF, SWINGING_BLADE_CONTENT_REF, CRUSHER_CONTENT_REF,
)
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink, ControlLink
from dnd.types.traps import TrapDamage, TrapPayload
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def mechanism_history(*, program: Literal["darts", "blade", "crusher", "door", "light"] = "darts",
                      jump: bool = False, save: bool = False, hidden_launcher: bool = False,
                      jump_release: bool = False) -> CapturedHistory:
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    if hidden_launcher:
        get_map().set_tile(4, 4, name="Wall", walking_cost=0, blocks_optics=True)
    try:
        actors = {}
        for role, position in (("traveler", (2, 2)), ("witness", (5, 3))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes", ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        if program in ("door", "light"):
            fixture = build_directional_door() if program == "door" else build_standing_torch()
            if program == "door":
                fixture.place_on_grid((6, 3), boundary_direction=CardinalDirection.EAST)
            else:
                fixture.place_on_grid((6, 3))
            link = ControlLink(target_item_uuid=fixture.uuid, target_kind=program)
        else:
            content, damage = {"darts": (DART_LAUNCHER_CONTENT_REF, DamageType.PIERCING),
                "blade": (SWINGING_BLADE_CONTENT_REF, DamageType.SLASHING),
                "crusher": (CRUSHER_CONTENT_REF, DamageType.BLUDGEONING)}[program]
            fixture = materialize_finite_trap((3, 5) if program == "darts" else (3, 2),
                geometry=LaneGeometry(range_feet=25) if program == "darts" else AreaGeometry(),
                direction=(0, -1) if program == "darts" else (1, 0),
                content_ref=content, avoidance=TrapSave(dc=12, retreat_on_success=program in ("blade", "crusher")),
                payload=TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=damage),)))
            link = ActivationLink(target_condition_uuid=fixture.uuid)
        plate = materialize_pressure_plate({(3, 2)}, link)
        encounter = Encounter(name="Pressure and mechanisms", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        encounter.start_encounter()
        encounter.start_turn()
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Mechanism room", start_cursor=0, end_cursor=baseline,
            observer_uuid=actors["traveler"].uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)

        def move(role, destination, jumping=False):
            actor = actors[role]
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            actor.update_entity_senses()
            with fixed_dice_faces(*([20 if save else 1] * 30)):
                result = (Jump(source_entity_uuid=actor.uuid, end_position=destination).apply() if jumping else
                    Move(source_entity_uuid=actor.uuid, end_position=destination,
                         path=[actor.position, destination], prefer_safe=False).apply())
            assert result is not None and not result.canceled, result.status_message if result else "Missing command"

        if jump:
            move("traveler", (4, 2), True)
            assert not plate.pressed
        move("traveler", (3, 2))
        retreats = save and program in ("blade", "crusher")
        assert plate.pressed is not retreats
        if program == "door":
            assert isinstance(fixture, DirectionalDoor)
            move("witness", (6, 3))
            move("traveler", (2, 2), jump_release)
            assert fixture.is_open and not plate.pressed
            move("witness", (7, 3), jump_release)
            assert not fixture.is_open
        else:
            if retreats:
                # The successful dodge really returned to (2,2); circle the
                # pressure cell before approaching it from the other side.
                move("traveler", (3, 1))
            move("traveler", (4, 2), jump_release)
        move("traveler", (3, 2))
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["traveler"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
