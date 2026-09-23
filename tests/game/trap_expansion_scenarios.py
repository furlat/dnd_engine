"""Recorded native jaw, gas and tripwire stories from both participants."""

from typing import Literal
from uuid import uuid4

from dnd.actions import Jump, Move
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.controller import HumanController
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.gas_traps import GasCloud, GasCloudSpec, GasVent, materialize_gas_vent
from dnd.spatial.jaws import ForceJawOpen, JawTrap, materialize_jaw_trap
from dnd.spatial.mechanisms import FiniteTrap, LaneGeometry, materialize_finite_trap
from dnd.spatial.triggers import materialize_pressure_plate, materialize_tripwire
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapState
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def trap_expansion_history(*, program: Literal["jaw", "gas", "tripwire"],
                           save: bool = False, jump: bool = False) -> CapturedHistory:
    """Execute game commands once; recording/renderer consumers replay the result."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    try:
        actors: dict[str, Entity] = {}
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
        traveler, witness = actors["traveler"], actors["witness"]
        lever = None
        plate = None
        fixture: JawTrap | GasVent | FiniteTrap
        if program == "jaw":
            fixture = materialize_jaw_trap((3, 2))
            lever = build_trap_lever(fixture.uuid, charges=-1, allow_activation=True)
            lever.place_on_grid((4, 3))
        elif program == "gas":
            fixture = materialize_gas_vent((4, 2), gas=GasCloudSpec(radius_feet=5, duration_rounds=3))
            plate = materialize_pressure_plate({(3, 2)}, ActivationLink(target_condition_uuid=fixture.uuid))
            lever = build_trap_lever(fixture.uuid, charges=-1, allow_activation=True)
            lever.place_on_grid((6, 3))
        else:
            fixture = materialize_finite_trap((3, 5), geometry=LaneGeometry(range_feet=25), direction=(0, -1))
            materialize_tripwire((2, 2), (3, 2), ActivationLink(target_condition_uuid=fixture.uuid))
        encounter = Encounter(name="Trap mechanisms", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Trap mechanisms", start_cursor=0, end_cursor=baseline,
            observer_uuid=traveler.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)

        def next_turn() -> None:
            with fixed_dice_faces(*((1, 4) * 20)):
                assert encounter.next_turn() is not None

        def take_turn(role: str) -> None:
            while encounter.get_current_entity() is not actors[role]:
                next_turn()

        def move(destination: tuple[int, int], *, faces: tuple[int, ...] = (), jumping: bool = False,
                 expected: tuple[int, int] | None = None) -> None:
            take_turn("traveler")
            traveler.update_entity_senses()
            with fixed_dice_faces(*faces):
                result = (Jump(source_entity_uuid=traveler.uuid, end_position=destination).apply() if jumping else
                    Move(source_entity_uuid=traveler.uuid, end_position=destination,
                         path=[traveler.position, destination], prefer_safe=False).apply())
            assert result is not None and not result.canceled, result.status_message if result else "Missing move"
            assert traveler.position == (expected if expected is not None else destination)

        def use_lever(name: str) -> None:
            assert lever is not None
            take_turn("witness")
            witness.update_entity_senses()
            assert name in {action.name for action in lever.get_use_actions(witness.uuid)}
            result = execute_use_action(witness, lever.uuid, name)
            assert result is not None and not result.canceled

        if program == "jaw":
            assert isinstance(fixture, JawTrap)
            faces = (20,) if save else (1, 4)
            move((3, 2), faces=faces, expected=(2, 2) if save else None)
            assert fixture.trap_state is TrapState.ACTIVATED
            assert ("Restrained" in traveler.active_conditions) is not save
            if not save:
                template = next(action for action in traveler.registered_actions if isinstance(action, ForceJawOpen))
                with fixed_dice_faces(20):
                    escaped = template.instantiate().apply()
                assert escaped is not None and not escaped.canceled
                assert traveler.action_economy.actions.normalized_score == 0
                assert "Restrained" not in traveler.active_conditions
            first_hp = traveler.get_hp()
            if not save:
                move((2, 2))
            move((3, 2))
            assert traveler.get_hp() == first_hp and not fixture.linked_conditions
            move((2, 2))
            use_lever("Reset Trap")
            assert fixture.trap_state is TrapState.READY
            move((3, 2), faces=faces, expected=(2, 2) if save else None)
            assert fixture.trap_state is TrapState.ACTIVATED
            assert traveler.get_hp() == (80 if save else 72)
            assert ("Restrained" in traveler.active_conditions) is not save
        elif program == "gas":
            assert isinstance(fixture, GasVent) and plate is not None
            move((3, 2), faces=(1, 4))
            released = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, GasCloud)]
            cloud, = released
            assert plate.pressed and traveler.get_hp() == 76
            move((4, 2))
            move((5, 2))
            move((5, 1))
            assert not plate.pressed and traveler.get_hp() == 76
            use_lever("Deactivate Trap")
            assert fixture.trap_state is TrapState.DEACTIVATED and cloud.is_active_spatial_condition()
            move((5, 2), faces=(1, 4))
            assert traveler.get_hp() == 72 and cloud.is_active_spatial_condition()
            next_turn()
            take_turn("traveler")
            assert traveler.get_hp() == 68  # The next native turn starts inside the lingering gas.
            move((5, 1))
            for _ in range(6):
                if not cloud.is_active_spatial_condition():
                    break
                next_turn()
            assert not cloud.is_active_spatial_condition()
            assert fixture.is_active_spatial_condition() and fixture.trap_state is TrapState.DEACTIVATED
            assert "Poisoned" not in traveler.active_conditions
        else:
            assert isinstance(fixture, FiniteTrap)
            hit = (20,) if save else (1, 4)
            move((3, 2), faces=() if jump else hit, jumping=jump)
            assert traveler.get_hp() == (80 if jump or save else 76)
            if jump:
                next_turn()  # Jump spends the bonus action; the return jump gets a real new turn.
            move((2, 2), jumping=jump)
            move((3, 2), faces=hit)
            assert traveler.get_hp() == (80 if save else 76 if jump else 72)
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["traveler"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
