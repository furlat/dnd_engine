"""Manual Chapter 26 checks for the agent tactical interface."""

import ast
import inspect

import ai.models as ai_models
import ai.interface as ai_interface
from ai.interface import LocalGameInterface
from ai.models import action_ev, attack_ev, crit_chance, hit_chance
from dnd.core.dice import fixed_dice_faces
from dnd.scenarios import agent_tactical_training
from dnd.scenarios.agent_tactical_training import (
    FirstAttackAgent,
    clear_melee_attack_modifier,
    create_agent_scene,
    make_melee_attack_auto_hit,
)


def test_local_game_interface_uses_top_level_engine_imports(capsys) -> None:
    """The public AI adapter keeps engine imports at module scope."""
    tree = ast.parse(inspect.getsource(ai_interface))
    late_imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            imports = [
                child for child in ast.walk(node)
                if isinstance(child, (ast.Import, ast.ImportFrom))
            ]
            late_imports.extend((node.name, import_node.lineno) for import_node in imports)

    assert late_imports == []

    readout_lines = [
        f"interface imports: late_imports={len(late_imports)}, adapter={LocalGameInterface.__name__}",
    ]
    expected_lines = [
        "interface imports: late_imports=0, adapter=LocalGameInterface",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_tactical_models_use_public_field_descriptions(capsys) -> None:
    """Agent-facing Pydantic models expose reader-facing field metadata."""
    source = inspect.getsource(ai_models)
    tactical_models = [
        ai_models.TacticalEntity,
        ai_models.DiceSpec,
        ai_models.AttackData,
        ai_models.SpellData,
        ai_models.TargetOption,
        ai_models.ActionOption,
        ai_models.ActionEconomy,
        ai_models.ActionResult,
        ai_models.TacticalState,
    ]

    assert "#" not in source
    assert ai_models.ActionEconomy().actions == 0
    assert ai_models.ActionEconomy().bonus_actions == 0
    assert ai_models.ActionEconomy().reactions == 0
    assert ai_models.ActionEconomy().movement == 0
    assert ai_models.SpellData().spell_level == 0

    missing_descriptions = [
        f"{model.__name__}.{field_name}"
        for model in tactical_models
        for field_name, field in model.model_fields.items()
        if not field.description
    ]
    field_count = sum(len(model.model_fields) for model in tactical_models)

    assert missing_descriptions == []

    readout_lines = [
        (
            "model hygiene: "
            f"models={len(tactical_models)}, "
            f"fields={field_count}, "
            f"missing_descriptions={len(missing_descriptions)}, "
            f"inline_comments={'#' in source}"
        ),
        (
            "defaults: "
            f"actions={ai_models.ActionEconomy().actions}, "
            f"bonus={ai_models.ActionEconomy().bonus_actions}, "
            f"reactions={ai_models.ActionEconomy().reactions}, "
            f"movement={ai_models.ActionEconomy().movement}, "
            f"spell_level={ai_models.SpellData().spell_level}"
        ),
    ]
    expected_lines = [
        "model hygiene: models=9, fields=86, missing_descriptions=0, inline_comments=False",
        "defaults: actions=0, bonus=0, reactions=0, movement=0, spell_level=0",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_agent_interface_reset_owns_the_training_runtime_state(capsys) -> None:
    """The agent scene reset names its own runtime state instead of delegating to test helpers."""
    source = inspect.getsource(agent_tactical_training.reset_agent_interface_state)

    required_fragments = [
        "EventQueue.reset()",
        "SpellProtectionRegistry.reset()",
        "BaseObject._registry.clear()",
        "BaseBlock._registry.clear()",
        "BaseCondition._registry.clear()",
        "BaseValue._registry.clear()",
        "Controller.clear_registry()",
        "Encounter.clear_registry()",
        "GridMap.reset()",
    ]

    assert "reset_combat_state" not in source
    for fragment in required_fragments:
        assert fragment in source

    scene = create_agent_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))

    assert state.me.uuid == str(scene.agent_actor.uuid)
    assert state.nearest_enemy() is not None

    readout_lines = [
        (
            "reset source: "
            f"reset_combat_state={'reset_combat_state' in source}, "
            f"required={sum(fragment in source for fragment in required_fragments)}/{len(required_fragments)}"
        ),
        (
            "post reset state: "
            f"actor={state.me.name}, "
            f"nearest={state.nearest_enemy().name if state.nearest_enemy() else None}, "
            f"position={state.me.position}"
        ),
    ]
    expected_lines = [
        "reset source: reset_combat_state=False, required=9/9",
        "post reset state: actor=Agent Skeleton, nearest=Training Hero, position=(2, 2)",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_tactical_interface_surface_exposes_state_scoring_and_training_helpers(capsys) -> None:
    """The tactical interface surface exposes state, scoring, and scene helpers."""
    scene = create_agent_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))

    assert isinstance(state, ai_models.TacticalState)
    assert state.me.name == "Agent Skeleton"
    assert state.nearest_enemy() is not None
    assert callable(hit_chance)
    assert callable(crit_chance)
    assert callable(attack_ev)
    assert callable(action_ev)
    assert callable(make_melee_attack_auto_hit)
    assert callable(clear_melee_attack_modifier)
    assert callable(agent_tactical_training.reset_agent_interface_state)
    assert FirstAttackAgent is not None

    readout_lines = [
        (
            "surface: "
            f"state={type(state).__name__}, "
            f"actor={state.me.name}, "
            f"nearest={state.nearest_enemy().name if state.nearest_enemy() else None}"
        ),
        (
            "scoring: "
            f"hit={callable(hit_chance)}, "
            f"crit={callable(crit_chance)}, "
            f"attack_ev={callable(attack_ev)}, "
            f"action_ev={callable(action_ev)}"
        ),
        (
            "training surfaces: "
            f"auto_hit={callable(make_melee_attack_auto_hit)}, "
            f"cleanup={callable(clear_melee_attack_modifier)}, "
            f"reset={callable(agent_tactical_training.reset_agent_interface_state)}, "
            f"agent={FirstAttackAgent.__name__}"
        ),
    ]
    expected_lines = [
        "surface: state=TacticalState, actor=Agent Skeleton, nearest=Training Hero",
        "scoring: hit=True, crit=True, attack_ev=True, action_ev=True",
        "training surfaces: auto_hit=True, cleanup=True, reset=True, agent=FirstAttackAgent",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_tactical_state_describes_the_agent_view(capsys) -> None:
    """LocalGameInterface builds a subjective tactical snapshot for one actor."""
    scene = create_agent_scene(target_position=(5, 2))
    interface = LocalGameInterface()

    state = interface.get_tactical_state(str(scene.agent_actor.uuid))

    assert state.me.uuid == str(scene.agent_actor.uuid)
    assert state.me.name == "Agent Skeleton"
    assert state.me.position == (2, 2)
    assert state.me.hp == scene.agent_actor.get_hp()
    assert state.action_economy.actions == 1
    assert state.action_economy.has_action
    assert state.action_economy.has_movement
    assert state.nearest_enemy() is not None
    assert state.nearest_enemy().uuid == str(scene.target.uuid)
    assert state.enemies[0].distance_feet == 15
    assert state.allies == []
    assert state.attacks
    assert state.movements
    assert state.self_actions
    assert not state.is_concentrating

    readout_lines = [
        (
            "me: "
            f"name={state.me.name}, pos={state.me.position}, "
            f"hp={state.me.hp}, ac={state.me.ac}, faction={state.me.faction}"
        ),
        (
            "economy: "
            f"actions={state.action_economy.actions}, "
            f"movement={state.action_economy.movement}, "
            f"has_action={state.action_economy.has_action}, "
            f"has_movement={state.action_economy.has_movement}"
        ),
        (
            "enemy: "
            f"name={state.nearest_enemy().name}, "
            f"pos={state.nearest_enemy().position}, "
            f"distance={state.enemies[0].distance_feet}, "
            f"allies={len(state.allies)}"
        ),
        (
            "choices: "
            f"attacks={len(state.attacks)}, "
            f"movements={len(state.movements)}, "
            f"self_actions={len(state.self_actions)}, "
            f"concentrating={state.is_concentrating}"
        ),
    ]
    expected_lines = [
        "me: name=Agent Skeleton, pos=(2, 2), hp=17, ac=0, faction=monsters",
        "economy: actions=1, movement=30, has_action=True, has_movement=True",
        "enemy: name=Training Hero, pos=(5, 2), distance=15, allies=0",
        "choices: attacks=1, movements=2, self_actions=3, concentrating=False",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_action_options_include_targets_and_combat_math(capsys) -> None:
    """Attack options carry target rows plus precomputed combat math."""
    scene = create_agent_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))

    attack_pair = state.find_attack_targeting(str(scene.target.uuid))

    assert attack_pair is not None
    attack, target_option = attack_pair
    assert attack.template_name == "Attack_MELEE_MAIN"
    assert attack.category == "attack"
    assert attack.target_type == "entity"
    assert attack.cost_type == "actions"
    assert attack.can_afford
    assert attack.weapon_slot == "MELEE_MAIN"
    assert attack.attack_data is not None
    assert attack.attack_data.damage_dice
    assert target_option.target_uuid == str(scene.target.uuid)
    assert target_option.target_name == "Training Hero"
    assert target_option.target_ac == scene.target.equipment.ac_bonus.normalized_score
    assert action_ev(attack, target_option) > 0

    readout_lines = [
        (
            "attack row: "
            f"template={attack.template_name}, "
            f"category={attack.category}, "
            f"target_type={attack.target_type}, "
            f"cost={attack.cost_type}:{attack.cost_amount}, "
            f"can_afford={attack.can_afford}"
        ),
        (
            "weapon math: "
            f"slot={attack.weapon_slot}, "
            f"weapon={attack.weapon_name}, "
            f"bonus={attack.attack_data.attack_bonus}, "
            f"dice={[(die.count, die.sides, die.bonus, die.damage_type) for die in attack.attack_data.damage_dice]}"
        ),
        (
            "target row: "
            f"index={target_option.index}, "
            f"name={target_option.target_name}, "
            f"ac={target_option.target_ac}, "
            f"distance={target_option.distance}, "
            f"ev={action_ev(attack, target_option):.2f}"
        ),
    ]
    expected_lines = [
        "attack row: template=Attack_MELEE_MAIN, category=attack, target_type=entity, cost=actions:1, can_afford=True",
        "weapon math: slot=MELEE_MAIN, weapon=Shortsword, bonus=4, dice=[(1, 6, 2, 'Piercing')]",
        "target row: index=0, name=Training Hero, ac=0, distance=5, ev=5.40",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_tactical_state_queries_find_enemy_actions_and_movement(capsys) -> None:
    """TacticalState queries select useful enemies, attacks, and movement."""
    scene = create_agent_scene(target_position=(6, 2))
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))

    nearest = state.nearest_enemy()
    weakest = state.weakest_enemy()
    move_toward = state.find_move_toward(str(scene.target.uuid))

    assert nearest is not None
    assert nearest.uuid == str(scene.target.uuid)
    assert weakest is not None
    assert weakest.uuid == str(scene.target.uuid)
    assert state.enemies_in_range(25)[0].uuid == str(scene.target.uuid)
    assert move_toward is not None
    assert move_toward[0].template_name == "Move"
    assert move_toward[1].position is not None

    old_distance = abs(scene.agent_actor.position[0] - scene.target.position[0]) + abs(
        scene.agent_actor.position[1] - scene.target.position[1]
    )
    new_distance = abs(move_toward[1].position[0] - scene.target.position[0]) + abs(
        move_toward[1].position[1] - scene.target.position[1]
    )

    assert new_distance < old_distance

    readout_lines = [
        (
            "queries: "
            f"nearest={nearest.name}, "
            f"weakest={weakest.name}, "
            f"in_25={[enemy.name for enemy in state.enemies_in_range(25)]}"
        ),
        (
            "move: "
            f"template={move_toward[0].template_name}, "
            f"index={move_toward[1].index}, "
            f"position={move_toward[1].position}, "
            f"path_cost={move_toward[1].path_cost}"
        ),
        f"distance: before={old_distance}, after={new_distance}, improved={new_distance < old_distance}",
    ]
    expected_lines = [
        "queries: nearest=Training Hero, weakest=Training Hero, in_25=['Training Hero']",
        "move: template=Move, index=27, position=(5, 2), path_cost=15",
        "distance: before=4, after=1, improved=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_expected_value_functions_score_attack_math(capsys) -> None:
    """Expected-value functions operate on tactical combat math snapshots."""
    scene = create_agent_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    attack, target_option = state.find_attack_targeting(str(scene.target.uuid))
    attack_data = attack.attack_data

    assert attack_data is not None
    normal_hit_chance = hit_chance(
        attack_data.attack_bonus,
        target_option.target_ac,
        attack_data.advantage,
    )
    advantage_hit_chance = hit_chance(
        attack_data.attack_bonus,
        target_option.target_ac,
        "advantage",
    )
    normal_crit_chance = crit_chance(attack_data.crit_threshold)
    attack_expected_damage = attack_ev(attack_data, target_option.target_ac)

    assert 0.05 <= normal_hit_chance <= 0.95
    assert advantage_hit_chance >= normal_hit_chance
    assert normal_crit_chance > 0
    assert attack_expected_damage > 0
    assert action_ev(attack, target_option) == attack_expected_damage

    readout_lines = [
        (
            "hit math: "
            f"bonus={attack_data.attack_bonus}, "
            f"target_ac={target_option.target_ac}, "
            f"normal={normal_hit_chance:.2f}, "
            f"advantage={advantage_hit_chance:.2f}"
        ),
        (
            "crit/ev: "
            f"crit={normal_crit_chance:.2f}, "
            f"attack_ev={attack_expected_damage:.2f}, "
            f"action_ev={action_ev(attack, target_option):.2f}"
        ),
    ]
    expected_lines = [
        "hit math: bonus=4, target_ac=0, normal=0.95, advantage=1.00",
        "crit/ev: crit=0.05, attack_ev=5.40, action_ev=5.40",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_local_interface_executes_selected_action_index(capsys) -> None:
    """The interface executes the selected template and target index."""
    scene = create_agent_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    attack, target_option = state.find_attack_targeting(str(scene.target.uuid))
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_target_hp = scene.target.get_hp()
    try:
        with fixed_dice_faces(10, 3):
            result = interface.execute(
                str(scene.agent_actor.uuid),
                attack.template_name,
                target_option.index,
            )
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    refreshed = interface.get_tactical_state(str(scene.agent_actor.uuid))

    assert result.success
    assert result.entity_hp == scene.agent_actor.get_hp()
    assert result.target_hp < initial_target_hp
    assert refreshed.action_economy.actions == 0
    assert not refreshed.action_economy.has_action

    readout_lines = [
        (
            "execute: "
            f"success={result.success}, "
            f"template={attack.template_name}, "
            f"target_index={target_option.index}, "
            f"actor_hp={result.entity_hp}"
        ),
        (
            "target hp: "
            f"before={initial_target_hp}, "
            f"after={result.target_hp}, "
            f"changed={result.target_hp < initial_target_hp}"
        ),
        (
            "refreshed economy: "
            f"actions={refreshed.action_economy.actions}, "
            f"has_action={refreshed.action_economy.has_action}"
        ),
    ]
    expected_lines = [
        "execute: success=True, template=Attack_MELEE_MAIN, target_index=0, actor_hp=17",
        "target hp: before=10, after=5, changed=True",
        "refreshed economy: actions=0, has_action=False",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_base_agent_runs_one_tactical_turn(capsys) -> None:
    """A BaseAgent subclass reads state and executes through the interface."""
    scene = create_agent_scene()
    interface = LocalGameInterface()
    agent = FirstAttackAgent(interface, str(scene.agent_actor.uuid))
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_target_hp = scene.target.get_hp()
    try:
        with fixed_dice_faces(10, 3):
            agent.run_turn()
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    refreshed = interface.get_tactical_state(str(scene.agent_actor.uuid))

    assert agent.actions_taken == 1
    assert scene.target.get_hp() < initial_target_hp
    assert refreshed.action_economy.actions == 0

    readout_lines = [
        (
            "agent turn: "
            f"actions_taken={agent.actions_taken}, "
            f"actor={scene.agent_actor.name}, "
            f"target={scene.target.name}"
        ),
        (
            "target hp: "
            f"before={initial_target_hp}, "
            f"after={scene.target.get_hp()}, "
            f"damaged={scene.target.get_hp() < initial_target_hp}"
        ),
        (
            "refreshed economy: "
            f"actions={refreshed.action_economy.actions}, "
            f"has_action={refreshed.action_economy.has_action}"
        ),
    ]
    expected_lines = [
        "agent turn: actions_taken=1, actor=Agent Skeleton, target=Training Hero",
        "target hp: before=10, after=5, damaged=True",
        "refreshed economy: actions=0, has_action=False",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
