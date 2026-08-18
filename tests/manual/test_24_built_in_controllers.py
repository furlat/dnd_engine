"""Manual Chapter 24 checks for built-in controllers and automated turns."""

from uuid import uuid4

from dnd.types.encounter_state import ControllerExecutionMode
from dnd.encounters.controllers import HumanController, PassController
from dnd.types.encounter_state import TurnState
from tests.manual.controller_test_support import (
    create_controller_pair,
    make_turn_context,
    reset_controller_catalogue_state,
    start_ordered_controller_encounter,
)


def test_controller_catalogue_exposes_controller_and_scene_surfaces(capsys) -> None:
    """The controller catalogue exposes the built-in controller tutorial surface."""
    reset_controller_catalogue_state()
    controllers = [
        HumanController(source_entity_uuid=uuid4()),
        PassController(source_entity_uuid=uuid4()),
    ]

    assert [controller.controller_type for controller in controllers] == [
        "human",
        "pass",
    ]
    assert [controller.execution_mode for controller in controllers] == [
        ControllerExecutionMode.EXTERNAL,
        ControllerExecutionMode.AUTONOMOUS,
    ]
    assert callable(create_controller_pair)
    assert callable(make_turn_context)
    assert callable(start_ordered_controller_encounter)

    readout_lines = [
        f"controllers: {[controller.controller_type for controller in controllers]}",
        (
            "catalogue functions: "
            f"pair={callable(create_controller_pair)}, "
            f"context={callable(make_turn_context)}, "
            f"encounter={callable(start_ordered_controller_encounter)}"
        ),
    ]
    expected_lines = [
        "controllers: ['human', 'pass']",
        "catalogue functions: pair=True, context=True, encounter=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"

def test_external_input_controller_stops_the_automatic_loop(capsys) -> None:
    """The human controller marks a turn that needs outside decisions."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    human_controller = HumanController(source_entity_uuid=hero.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        human_controller,
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    human_result = encounter.advance_until_external_boundary()
    human_context = make_turn_context(hero)

    assert human_result.status == "waiting_for_human"
    assert human_result.entity_uuid == hero.uuid
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert not human_controller.can_continue_turn(hero, human_context)
    assert human_controller.get_next_action(hero, human_context) is None
    human_current = encounter.get_current_entity()
    assert human_current is not None
    human_readout = [
        (
            "human wait: "
            f"status={human_result.status}, "
            f"entity={human_result.entity_name}, "
            f"current={human_current.name}, "
            f"turn_state={encounter.turn_state.value}, "
            f"can_continue={human_controller.can_continue_turn(hero, human_context)}"
        ),
        f"human action: {human_controller.get_next_action(hero, human_context)}",
    ]

    readout_lines = human_readout
    expected_lines = [
        "human wait: status=waiting_for_human, entity=Controller Hero, current=Controller Hero, turn_state=in_progress, can_continue=False",
        "human action: None",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_pass_controller_finishes_an_automated_turn_immediately(capsys) -> None:
    """Pass controllers consume the turn boundary without choosing an action."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=monster,
    )

    result = encounter.advance_until_external_boundary()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert encounter.combatants[monster.uuid].has_acted_this_round
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    current = encounter.get_current_entity()
    assert current is not None

    readout_lines = [
        (
            "pass turn: "
            f"status={result.status}, "
            f"next={result.entity_name}, "
            f"monster_turns={encounter.combatants[monster.uuid].turn_count}, "
            f"acted={encounter.combatants[monster.uuid].has_acted_this_round}"
        ),
        f"current: actor={current.name}, turn_state={encounter.turn_state.value}",
    ]
    expected_lines = [
        "pass turn: status=waiting_for_human, next=Controller Hero, monster_turns=1, acted=True",
        "current: actor=Controller Hero, turn_state=in_progress",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_one_controller_boundary_advances_at_most_one_autonomous_turn() -> None:
    """The server coordinator can yield between independently completed turns."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    first = encounter.advance_one_controller_boundary()

    assert first.status == "advanced_autonomous"
    assert encounter.combatants[hero.uuid].turn_count == 1
    assert encounter.combatants[monster.uuid].turn_count == 0
    assert encounter.get_current_entity() is monster
    assert encounter.turn_state == TurnState.NOT_STARTED

    second = encounter.advance_one_controller_boundary()

    assert second.status == "advanced_autonomous"
    assert encounter.combatants[monster.uuid].turn_count == 1


def test_one_controller_boundary_starts_and_returns_external_turn() -> None:
    """An external boundary starts once without executing another combatant."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    result = encounter.advance_one_controller_boundary()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert encounter.turn_state is TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 0
