"""Manual Chapter 24 checks for built-in controllers and automated turns."""

from uuid import uuid4

from dnd.controller import (
    AIAgentController,
    CodexController,
    ExternalAIController,
    HumanController,
    PassController,
)
from dnd.encounter import TurnState
from dnd.scenarios.controller_catalogue import (
    RecordingTurnRunner,
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
        CodexController(source_entity_uuid=uuid4()),
        PassController(source_entity_uuid=uuid4()),
        AIAgentController(source_entity_uuid=uuid4()),
    ]
    runner = RecordingTurnRunner()

    assert [controller.controller_type for controller in controllers] == [
        "human",
        "codex",
        "pass",
        "ai_agent",
    ]
    assert runner.run_count == 0
    assert callable(create_controller_pair)
    assert callable(make_turn_context)
    assert callable(start_ordered_controller_encounter)

    readout_lines = [
        f"controllers: {[controller.controller_type for controller in controllers]}",
        f"runner: type={runner.__class__.__name__}, run_count={runner.run_count}",
        (
            "catalogue functions: "
            f"pair={callable(create_controller_pair)}, "
            f"context={callable(make_turn_context)}, "
            f"encounter={callable(start_ordered_controller_encounter)}"
        ),
    ]
    expected_lines = [
        "controllers: ['human', 'codex', 'pass', 'ai_agent']",
        "runner: type=RecordingTurnRunner, run_count=0",
        "catalogue functions: pair=True, context=True, encounter=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_external_input_controllers_stop_the_automatic_loop(capsys) -> None:
    """Human and Codex controllers mark turns that need outside decisions."""
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

    human_result = encounter.advance_until_player()
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

    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    codex_controller = CodexController(source_entity_uuid=hero.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        codex_controller,
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    codex_result = encounter.advance_until_player()
    codex_context = make_turn_context(hero)

    assert codex_result.status == "waiting_for_codex"
    assert codex_result.entity_uuid == hero.uuid
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert not codex_controller.can_continue_turn(hero, codex_context)
    assert codex_controller.get_next_action(hero, codex_context) is None
    codex_current = encounter.get_current_entity()
    assert codex_current is not None

    readout_lines = [
        *human_readout,
        (
            "codex wait: "
            f"status={codex_result.status}, "
            f"entity={codex_result.entity_name}, "
            f"current={codex_current.name}, "
            f"turn_state={encounter.turn_state.value}, "
            f"can_continue={codex_controller.can_continue_turn(hero, codex_context)}"
        ),
        f"codex action: {codex_controller.get_next_action(hero, codex_context)}",
    ]
    expected_lines = [
        "human wait: status=waiting_for_human, entity=Controller Hero, current=Controller Hero, turn_state=in_progress, can_continue=False",
        "human action: None",
        "codex wait: status=waiting_for_codex, entity=Controller Hero, current=Controller Hero, turn_state=in_progress, can_continue=False",
        "codex action: None",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_external_ai_controller_waits_for_subprocess_input(capsys) -> None:
    """External AI controllers stop the encounter loop until the subprocess acts."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    external_controller = ExternalAIController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        external_controller,
        first_actor=monster,
    )

    result = encounter.advance_until_player()
    context = make_turn_context(monster)

    assert external_controller.controller_type == "external_ai"
    assert result.status == "waiting_for_ai"
    assert result.entity_uuid == monster.uuid
    assert encounter.get_current_entity() is monster
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert not external_controller.can_continue_turn(monster, context)
    assert external_controller.get_next_action(monster, context) is None
    current = encounter.get_current_entity()
    assert current is not None

    readout_lines = [
        (
            "external ai wait: "
            f"status={result.status}, "
            f"entity={result.entity_name}, "
            f"current={current.name}, "
            f"turn_state={encounter.turn_state.value}, "
            f"can_continue={external_controller.can_continue_turn(monster, context)}"
        ),
        f"external ai action: {external_controller.get_next_action(monster, context)}",
    ]
    expected_lines = [
        "external ai wait: status=waiting_for_ai, entity=Controller Skeleton, current=Controller Skeleton, turn_state=in_progress, can_continue=False",
        "external ai action: None",
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

    result = encounter.advance_until_player()

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


def test_ai_agent_controller_delegates_once_per_turn(capsys) -> None:
    """Agent controllers run the bound turn runner once for each owned turn."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair(monster_position=(4, 1))
    runner = RecordingTurnRunner()
    agent_controller = AIAgentController(source_entity_uuid=monster.uuid)
    agent_controller.set_agent(runner)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        agent_controller,
        first_actor=monster,
    )

    encounter.run_turn()

    assert runner.run_count == 1
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert encounter.get_current_entity() is hero
    first_turn_count = encounter.combatants[monster.uuid].turn_count
    first_current = encounter.get_current_entity()
    assert first_current is not None
    first_current_name = first_current.name

    encounter.run_turn()
    encounter.run_turn()

    assert runner.run_count == 2
    assert encounter.combatants[monster.uuid].turn_count == 2
    second_current = encounter.get_current_entity()
    assert second_current is not None

    readout_lines = [
        (
            "first delegation: "
            f"runner={runner.__class__.__name__}, "
            f"run_count=1, "
            f"monster_turns={first_turn_count}, "
            f"current={first_current_name}"
        ),
        (
            "second delegation: "
            f"run_count={runner.run_count}, "
            f"monster_turns={encounter.combatants[monster.uuid].turn_count}, "
            f"current={second_current.name}"
        ),
    ]
    expected_lines = [
        "first delegation: runner=RecordingTurnRunner, run_count=1, monster_turns=1, current=Controller Hero",
        "second delegation: run_count=2, monster_turns=2, current=Controller Hero",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
