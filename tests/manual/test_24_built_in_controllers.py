"""Manual Chapter 24 checks for built-in controllers and automated turns."""

from uuid import uuid4

from dnd.actions import Attack, Move
from dnd.controller import (
    AIAgentController,
    CodexController,
    HumanController,
    MeleeAIController,
    PassController,
)
from dnd.core.events import WeaponSlot
from dnd.encounter import TurnState
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin
from dnd.scenarios.controller_catalogue import (
    RecordingTurnRunner,
    create_controller_pair,
    create_melee_only_skeleton,
    make_turn_context,
    manhattan_distance,
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
        MeleeAIController(source_entity_uuid=uuid4()),
        AIAgentController(source_entity_uuid=uuid4()),
    ]
    runner = RecordingTurnRunner()

    assert [controller.controller_type for controller in controllers] == [
        "human",
        "codex",
        "pass",
        "melee_ai",
        "ai_agent",
    ]
    assert runner.run_count == 0
    assert callable(create_controller_pair)
    assert callable(create_melee_only_skeleton)
    assert callable(make_turn_context)
    assert callable(start_ordered_controller_encounter)

    readout_lines = [
        f"controllers: {[controller.controller_type for controller in controllers]}",
        f"runner: type={runner.__class__.__name__}, run_count={runner.run_count}",
        (
            "catalogue functions: "
            f"pair={callable(create_controller_pair)}, "
            f"melee_skeleton={callable(create_melee_only_skeleton)}, "
            f"context={callable(make_turn_context)}, "
            f"encounter={callable(start_ordered_controller_encounter)}"
        ),
    ]
    expected_lines = [
        "controllers: ['human', 'codex', 'pass', 'melee_ai', 'ai_agent']",
        "runner: type=RecordingTurnRunner, run_count=0",
        "catalogue functions: pair=True, melee_skeleton=True, context=True, encounter=True",
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
    human_readout = [
        (
            "human wait: "
            f"status={human_result.status}, "
            f"entity={human_result.entity_name}, "
            f"current={encounter.get_current_entity().name}, "
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

    readout_lines = [
        *human_readout,
        (
            "codex wait: "
            f"status={codex_result.status}, "
            f"entity={codex_result.entity_name}, "
            f"current={encounter.get_current_entity().name}, "
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

    readout_lines = [
        (
            "pass turn: "
            f"status={result.status}, "
            f"next={result.entity_name}, "
            f"monster_turns={encounter.combatants[monster.uuid].turn_count}, "
            f"acted={encounter.combatants[monster.uuid].has_acted_this_round}"
        ),
        f"current: actor={encounter.get_current_entity().name}, turn_state={encounter.turn_state.value}",
    ]
    expected_lines = [
        "pass turn: status=waiting_for_human, next=Controller Hero, monster_turns=1, acted=True",
        "current: actor=Controller Hero, turn_state=in_progress",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_melee_ai_prefers_a_weapon_attack_when_adjacent(capsys) -> None:
    """Melee AI chooses a weapon attack before other entity-targeted actions."""
    reset_controller_catalogue_state()
    skeleton = create_melee_only_skeleton(
        name="AI Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    hero = create_goblin(name="Adjacent Hero", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    controller = MeleeAIController(source_entity_uuid=skeleton.uuid)
    context = make_turn_context(skeleton)
    action = controller.get_next_action(skeleton, context)

    assert isinstance(action, Attack)
    assert action.name == "Attack_MELEE_MAIN"
    assert action.weapon_slot == WeaponSlot.MELEE_MAIN
    assert action.target_entity_uuid == hero.uuid

    readout_lines = [
        (
            "attack choice: "
            f"type={type(action).__name__}, "
            f"name={action.name}, "
            f"slot={action.weapon_slot.value}, "
            f"target={Entity.get(action.target_entity_uuid).name}"
        ),
        (
            "tactical context: "
            f"visible_enemies={len(context.visible_enemies)}, "
            f"visible_allies={len(context.visible_allies)}, "
            f"actor={skeleton.name}"
        ),
    ]
    expected_lines = [
        "attack choice: type=Attack, name=Attack_MELEE_MAIN, slot=MELEE_MAIN, target=Adjacent Hero",
        "tactical context: visible_enemies=1, visible_allies=0, actor=AI Skeleton",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_melee_ai_moves_closer_when_no_attack_is_in_range(capsys) -> None:
    """Melee AI chooses a legal move target that reduces enemy distance."""
    reset_controller_catalogue_state()
    skeleton = create_melee_only_skeleton(
        name="AI Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    hero = create_goblin(name="Distant Hero", position=(5, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    controller = MeleeAIController(source_entity_uuid=skeleton.uuid)
    action = controller.get_next_action(skeleton, make_turn_context(skeleton))
    start_distance = manhattan_distance(skeleton.position, hero.position)

    assert isinstance(action, Move)
    assert action.end_position is not None
    assert action.path is not None
    assert action.path[0] == skeleton.position
    assert action.path[-1] == action.end_position
    end_distance = manhattan_distance(action.end_position, hero.position)
    assert end_distance < start_distance

    readout_lines = [
        (
            "move choice: "
            f"type={type(action).__name__}, "
            f"start={skeleton.position}, "
            f"end={action.end_position}, "
            f"path={action.path}"
        ),
        f"distance: before={start_distance}, after={end_distance}, improved={end_distance < start_distance}",
    ]
    expected_lines = [
        "move choice: type=Move, start=(1, 1), end=(4, 1), path=[(1, 1), (2, 1), (3, 1), (4, 1)]",
        "distance: before=4, after=1, improved=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_melee_ai_passes_when_no_enemy_is_visible(capsys) -> None:
    """Melee AI returns no action when it has no visible enemy to pursue."""
    reset_controller_catalogue_state()
    skeleton = create_melee_only_skeleton(
        name="Lone AI Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=20)

    controller = MeleeAIController(source_entity_uuid=skeleton.uuid)
    context = make_turn_context(skeleton)
    action = controller.get_next_action(skeleton, context)

    assert context.visible_enemies == {}
    assert action is None

    readout_lines = [
        f"target list: visible_enemies={len(context.visible_enemies)}, visible_allies={len(context.visible_allies)}",
        f"pass signal: action={action}, controller={controller.controller_type}",
    ]
    expected_lines = [
        "target list: visible_enemies=0, visible_allies=0",
        "pass signal: action=None, controller=melee_ai",
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
    first_current_name = encounter.get_current_entity().name

    encounter.run_turn()
    encounter.run_turn()

    assert runner.run_count == 2
    assert encounter.combatants[monster.uuid].turn_count == 2

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
            f"current={encounter.get_current_entity().name}"
        ),
    ]
    expected_lines = [
        "first delegation: runner=RecordingTurnRunner, run_count=1, monster_turns=1, current=Controller Hero",
        "second delegation: run_count=2, monster_turns=2, current=Controller Hero",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
