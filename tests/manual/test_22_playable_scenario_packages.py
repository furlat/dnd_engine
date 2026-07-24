"""Manual Chapter 22 checks for playable scenario packages."""

from uuid import uuid4

from dnd.core.dice import fixed_dice_faces
from dnd.core.life_types import LifeState
from dnd.core.modifiers import DamageType
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.scenarios.gatehouse import (
    ScenarioHumanController,
    ScenarioPassController,
    add_melee_auto_hit,
    create_gatehouse_scenario,
    remove_melee_auto_hit,
    reset_playable_scenario_state,
)


def test_scenario_package_exposes_expected_surfaces(capsys) -> None:
    """The scenario package exposes controllers, reset, and factory surfaces."""
    reset_playable_scenario_state()
    human_controller = ScenarioHumanController(source_entity_uuid=uuid4())
    pass_controller = ScenarioPassController(source_entity_uuid=uuid4())

    assert human_controller.controller_type == "human"
    assert pass_controller.controller_type == "pass"
    assert callable(reset_playable_scenario_state)
    assert callable(create_gatehouse_scenario)
    assert callable(add_melee_auto_hit)
    assert callable(remove_melee_auto_hit)

    readout_lines = [
        f"controllers: human={human_controller.controller_type}, pass={pass_controller.controller_type}",
        (
            "package functions: "
            f"reset={'yes' if callable(reset_playable_scenario_state) else 'no'}, "
            f"factory={'yes' if callable(create_gatehouse_scenario) else 'no'}, "
            f"auto_hit={'yes' if callable(add_melee_auto_hit) else 'no'}, "
            f"cleanup={'yes' if callable(remove_melee_auto_hit) else 'no'}"
        ),
    ]
    expected_lines = [
        "controllers: human=human, pass=pass",
        "package functions: reset=yes, factory=yes, auto_hit=yes, cleanup=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_scenario_factory_builds_map_actors_controllers_and_active_encounter(capsys) -> None:
    """A scenario package composes world, actors, controllers, and encounter state."""
    scenario = create_gatehouse_scenario()

    assert scenario.encounter.state == EncounterState.ACTIVE
    assert Encounter.get_active() is scenario.encounter
    assert scenario.encounter.turn_state == TurnState.NOT_STARTED
    assert scenario.encounter.round_number == 1
    assert scenario.encounter.initiative_order == [
        scenario.monster.uuid,
        scenario.hero.uuid,
    ]
    assert scenario.hero.faction == "heroes"
    assert scenario.monster.faction == "monsters"
    assert scenario.hero_controller.controller_type == "human"
    assert scenario.monster_controller.controller_type == "pass"
    assert scenario.hero_controller.encounter_start_names == ["Gatehouse Hero"]
    assert scenario.monster.uuid in scenario.hero.senses.entities

    readout_lines = [
        (
            "encounter: "
            f"name={scenario.encounter.name}, "
            f"state={scenario.encounter.state.value}, "
            f"turn_state={scenario.encounter.turn_state.value}, "
            f"round={scenario.encounter.round_number}"
        ),
        f"initiative: {[scenario.monster.name, scenario.hero.name]}, active={'yes' if Encounter.get_active() is scenario.encounter else 'no'}",
        f"actors: hero={scenario.hero.name}/{scenario.hero.faction}, monster={scenario.monster.name}/{scenario.monster.faction}",
        (
            "controllers: "
            f"hero={scenario.hero_controller.controller_type}, "
            f"monster={scenario.monster_controller.controller_type}, "
            f"start={scenario.hero_controller.encounter_start_names}"
        ),
        f"senses: hero_sees_monster={'yes' if scenario.monster.uuid in scenario.hero.senses.entities else 'no'}",
    ]
    expected_lines = [
        "encounter: name=Gatehouse Scenario, state=active, turn_state=not_started, round=1",
        "initiative: ['Gatehouse Skeleton', 'Gatehouse Hero'], active=yes",
        "actors: hero=Gatehouse Hero/heroes, monster=Gatehouse Skeleton/monsters",
        "controllers: hero=human, monster=pass, start=['Gatehouse Hero']",
        "senses: hero_sees_monster=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_automated_turns_advance_until_the_human_actor_needs_input(capsys) -> None:
    """The encounter can run automated turns until a human turn begins."""
    scenario = create_gatehouse_scenario()

    result = scenario.encounter.advance_until_player()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == scenario.hero.uuid
    assert result.entity_name == "Gatehouse Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert scenario.encounter.get_current_entity() is scenario.hero
    assert scenario.encounter.turn_state == TurnState.IN_PROGRESS
    assert scenario.monster_controller.turn_start_names == ["Gatehouse Skeleton"]
    assert scenario.monster_controller.turn_end_names == ["Gatehouse Skeleton"]
    assert scenario.hero_controller.turn_start_contexts[-1].entity_uuid == scenario.hero.uuid
    assert scenario.monster.uuid in scenario.hero_controller.turn_start_contexts[-1].visible_enemies
    context = scenario.hero_controller.turn_start_contexts[-1]

    readout_lines = [
        f"advance: status={result.status}, entity={result.entity_name}, round={result.round_number}, index={result.turn_index}",
        (
            "encounter turn: "
            f"current={scenario.encounter.get_current_entity().name}, "
            f"state={scenario.encounter.turn_state.value}"
        ),
        (
            "automated turn: "
            f"starts={scenario.monster_controller.turn_start_names}, "
            f"ends={scenario.monster_controller.turn_end_names}"
        ),
        (
            "human context: "
            f"actor={scenario.hero.name}, "
            f"visible_enemies={len(context.visible_enemies)}, "
            f"sees_monster={'yes' if scenario.monster.uuid in context.visible_enemies else 'no'}"
        ),
    ]
    expected_lines = [
        "advance: status=waiting_for_human, entity=Gatehouse Hero, round=1, index=1",
        "encounter turn: current=Gatehouse Hero, state=in_progress",
        "automated turn: starts=['Gatehouse Skeleton'], ends=['Gatehouse Skeleton']",
        "human context: actor=Gatehouse Hero, visible_enemies=1, sees_monster=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_human_action_execution_uses_indexed_discovery_and_captures_combat_log(capsys) -> None:
    """A scenario can execute a selected action and capture its combat log."""
    scenario = create_gatehouse_scenario()
    scenario.encounter.advance_until_player()
    hp_before = scenario.monster.get_hp()
    modifier_uuid = add_melee_auto_hit(scenario.hero)

    try:
        with fixed_dice_faces(12, 4):
            event = scenario.encounter.execute_action(
                scenario.hero.uuid,
                "Attack_MELEE_MAIN",
                0,
            )
    finally:
        remove_melee_auto_hit(scenario.hero, modifier_uuid)

    assert event is not None
    assert not event.canceled
    assert scenario.monster.get_hp() < hp_before
    assert scenario.encounter.combat_log
    assert scenario.encounter.get_combat_log(since=0)[-1] is scenario.encounter.combat_log[-1]
    assert scenario.encounter.combat_log[-1].source_uuid == str(scenario.hero.uuid)
    latest_log = scenario.encounter.combat_log[-1]

    readout_lines = [
        (
            "execute: "
            f"event={event.event_type.value if event else 'none'}, "
            f"phase={event.phase.value if event else 'none'}, "
            f"canceled={'yes' if event and event.canceled else 'no'}"
        ),
        (
            "damage: "
            f"hp={hp_before}->{scenario.monster.get_hp()}, "
            f"log_entries={len(scenario.encounter.combat_log)}, "
            f"latest={latest_log.entry_type.value}"
        ),
        (
            "combat log: "
            f"source_matches={'yes' if latest_log.source_uuid == str(scenario.hero.uuid) else 'no'}, "
            f"since_latest={'yes' if scenario.encounter.get_combat_log(since=0)[-1] is latest_log else 'no'}"
        ),
    ]
    expected_lines = [
        "execute: event=attack, phase=completion, canceled=no",
        "damage: hp=17->11, log_entries=4, latest=attack",
        "combat log: source_matches=yes, since_latest=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_scenario_ends_when_one_faction_has_survivors(capsys) -> None:
    """The videogame encounter ends by surviving faction state."""
    scenario = create_gatehouse_scenario()
    hp_before = scenario.monster.get_hp()

    scenario.monster.health.take_damage(
        scenario.monster.get_hp(),
        DamageType.FORCE,
        scenario.hero.uuid,
    )
    death_events = scenario.encounter.check_deaths()

    assert death_events
    assert scenario.encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert scenario.hero_controller.encounter_end_names == ["Gatehouse Hero"]
    assert scenario.encounter.get_alive_combatants()[0].entity_uuid == scenario.hero.uuid
    assert scenario.encounter.get_dead_combatants()[0].entity_uuid == scenario.monster.uuid
    assert scenario.monster.health.life_state is LifeState.DEAD
    alive = scenario.encounter.get_alive_combatants()
    dead = scenario.encounter.get_dead_combatants()

    readout_lines = [
        (
            "death check: "
            f"hp={hp_before}->{scenario.monster.get_hp()}, "
            f"events={len(death_events)}, "
            f"life_state={scenario.monster.health.life_state.value}"
        ),
        (
            "encounter end: "
            f"state={scenario.encounter.state.value}, "
            f"active={'yes' if Encounter.get_active() is scenario.encounter else 'no'}, "
            f"end_callbacks={scenario.hero_controller.encounter_end_names}"
        ),
        (
            "survivors: "
            f"alive={[combatant.entity.name for combatant in alive]}, "
            f"dead={[combatant.entity.name for combatant in dead]}"
        ),
    ]
    expected_lines = [
        "death check: hp=17->0, events=1, life_state=dead",
        "encounter end: state=ended, active=no, end_callbacks=['Gatehouse Hero']",
        "survivors: alive=['Gatehouse Hero'], dead=['Gatehouse Skeleton']",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
