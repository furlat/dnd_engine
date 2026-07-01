"""Manual Chapter 27 checks for agent decision patterns."""

import inspect
from uuid import uuid4

import ai.agents.base as ai_agent_base
import ai.agents.examples as ai_agent_examples
import ai.composites as ai_composites
import ai.primitives.behavior_tree as ai_behavior_tree
import ai.primitives.state_machine as ai_state_machine
import ai.primitives.utility as ai_utility
from ai.agents.base import UtilityAgent
from ai.agents.examples import create_melee_fighter_bt
from ai.composites import InterruptType, MoveAndAttack, detect_interrupts
from dnd.core.dice import fixed_dice_faces
from dnd.scenarios import agent_decision_training
from dnd.scenarios.agent_decision_training import (
    create_decision_scene,
    create_two_target_scene,
)
from dnd.scenarios.agent_tactical_training import (
    clear_melee_attack_modifier,
    make_melee_attack_auto_hit,
    reset_agent_interface_state,
)
from ai.interface import LocalGameInterface
from ai.models import ActionResult, TacticalEntity
from ai.primitives.behavior_tree import (
    BTAction,
    BTContext,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
    attack_nearest,
    dodge_action,
    has_affordable_attack,
)
from ai.primitives.utility import DamageScorer, FocusFireScorer, UtilityAI


def test_decision_layer_uses_docstrings_and_field_descriptions() -> None:
    """The public decision layer avoids comment scaffolding and exposes model metadata."""
    modules = [
        ai_agent_base,
        ai_agent_examples,
        ai_composites,
        ai_behavior_tree,
        ai_state_machine,
        ai_utility,
    ]
    model_classes = [
        ai_composites.CompositeResult,
        ai_utility.ScoredOption,
    ]
    field_count = sum(len(model.model_fields) for model in model_classes)

    for module in modules:
        source = inspect.getsource(module)
        assert "#" not in source
        assert "..." not in source

    for model in model_classes:
        for field_name, field in model.model_fields.items():
            assert field.description, f"{model.__name__}.{field_name}"

    readout_lines = [
        f"hygiene modules: scanned={len(modules)}, comments_or_ellipsis=0",
        (
            f"constants: max_turn_iterations={ai_agent_base.MAX_TURN_ITERATIONS}, "
            f"any_state={ai_state_machine.ANY_STATE}"
        ),
        f"model field descriptions: present={field_count}, missing=0",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "hygiene modules: scanned=6, comments_or_ellipsis=0",
        "constants: max_turn_iterations=20, any_state=*",
        "model field descriptions: present=8, missing=0",
    ]
    assert readout_lines == expected_lines


def test_decision_scenes_reuse_the_visible_tactical_reset_surface() -> None:
    """Decision scene factories reuse the documented tactical reset."""
    module_source = inspect.getsource(agent_decision_training)
    one_target_source = inspect.getsource(agent_decision_training.create_decision_scene)
    two_target_source = inspect.getsource(agent_decision_training.create_two_target_scene)

    assert "reset_combat_state" not in module_source
    assert "reset_agent_interface_state()" in one_target_source
    assert "reset_agent_interface_state()" in two_target_source

    scene = create_decision_scene()
    two_target_scene = create_two_target_scene()

    assert scene.agent_actor.name == "Decision Skeleton"
    assert scene.encounter.name == "Agent Decision Encounter"
    assert two_target_scene.encounter.name == "Agent Utility Encounter"

    readout_lines = [
        (
            "reset source: "
            f"direct_reset={'reset_combat_state' in module_source}, "
            f"one_target_reuses={'reset_agent_interface_state()' in one_target_source}, "
            f"two_target_reuses={'reset_agent_interface_state()' in two_target_source}"
        ),
        (
            f"one-target scene: actor={scene.agent_actor.name}, "
            f"target={scene.target.name}, encounter={scene.encounter.name}"
        ),
        (
            f"two-target scene: weak={two_target_scene.weak_target.name}:"
            f"{two_target_scene.weak_target.get_hp()}, "
            f"sturdy={two_target_scene.sturdy_target.name}:"
            f"{two_target_scene.sturdy_target.get_hp()}, "
            f"encounter={two_target_scene.encounter.name}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "reset source: direct_reset=False, one_target_reuses=True, two_target_reuses=True",
        "one-target scene: actor=Decision Skeleton, target=Decision Hero, encounter=Agent Decision Encounter",
        "two-target scene: weak=Wounded Hero:7, sturdy=Sturdy Hero:10, encounter=Agent Utility Encounter",
    ]
    assert readout_lines == expected_lines


def test_decision_surface_example_imports_live_patterns() -> None:
    """EB-27-001 imports the live decision-pattern surface."""
    scene = create_decision_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    two_target_scene = create_two_target_scene()

    nearest = state.nearest_enemy()
    utility_target_names = [
        two_target_scene.weak_target.name,
        two_target_scene.sturdy_target.name,
    ]
    readout_lines = [
        (
            f"surface: actor={state.me.name}, nearest={nearest.name}, "
            f"utility_targets={utility_target_names}"
        ),
        (
            f"state rows: attacks={len(state.attacks)}, "
            f"movements={len(state.movements)}, "
            f"self_actions={len(state.self_actions)}, spells={len(state.spells)}"
        ),
        (
            f"patterns: bt={Selector is not None}, "
            f"composite={MoveAndAttack is not None}, "
            f"interrupts={callable(detect_interrupts)}, "
            f"utility={UtilityAI is not None}, agent={UtilityAgent is not None}"
        ),
        (
            f"training surfaces: auto_hit={callable(make_melee_attack_auto_hit)}, "
            f"cleanup={callable(clear_melee_attack_modifier)}, "
            f"reset={callable(reset_agent_interface_state)}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "surface: actor=Decision Skeleton, nearest=Decision Hero, utility_targets=['Wounded Hero', 'Sturdy Hero']",
        "state rows: attacks=1, movements=2, self_actions=3, spells=0",
        "patterns: bt=True, composite=True, interrupts=True, utility=True, agent=True",
        "training surfaces: auto_hit=True, cleanup=True, reset=True",
    ]
    assert nearest is not None
    assert readout_lines == expected_lines


def test_behavior_tree_selector_attacks_and_refreshes_state() -> None:
    """A selector can prioritize an affordable attack and refresh state."""
    scene = create_decision_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    tree = Selector([
        Sequence([
            Condition(has_affordable_attack),
            BTAction(attack_nearest),
        ]),
        BTAction(dodge_action),
    ])
    context = BTContext(interface, state, str(scene.agent_actor.uuid), blackboard={})
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_target_hp = scene.target.get_hp()
    try:
        with fixed_dice_faces(3, 3, 3, 3):
            result = tree.tick(context)
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    readout_lines = [
        (
            f"tree: result={result.value}, actor={context.state.me.name}, "
            f"nearest={state.nearest_enemy().name}"
        ),
        (
            f"target hp: before={initial_target_hp}, after={scene.target.get_hp()}, "
            f"damaged={scene.target.get_hp() < initial_target_hp}"
        ),
        (
            f"economy: actions={context.state.action_economy.actions}, "
            f"has_attack={context.state.has_affordable_attack()}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "tree: result=success, actor=Decision Skeleton, nearest=Decision Hero",
        "target hp: before=10, after=5, damaged=True",
        "economy: actions=0, has_attack=False",
    ]
    assert result == NodeStatus.SUCCESS
    assert readout_lines == expected_lines


def test_melee_fighter_factory_moves_and_attacks_when_needed() -> None:
    """The ready-made melee fighter behavior can close distance and attack."""
    scene = create_decision_scene(target_position=(5, 2))
    interface = LocalGameInterface()
    agent = create_melee_fighter_bt(interface, str(scene.agent_actor.uuid))
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_position = scene.agent_actor.position
    initial_target_hp = scene.target.get_hp()
    try:
        with fixed_dice_faces(3, 3, 3, 3):
            agent.run_turn()
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    refreshed = interface.get_tactical_state(str(scene.agent_actor.uuid))
    adjacent = max(
        abs(scene.agent_actor.position[0] - scene.target.position[0]),
        abs(scene.agent_actor.position[1] - scene.target.position[1]),
    ) == 1
    readout_lines = [
        (
            f"fighter: start={initial_position}, end={scene.agent_actor.position}, "
            f"target={scene.target.name}"
        ),
        (
            f"target hp: before={initial_target_hp}, after={scene.target.get_hp()}, "
            f"damaged={scene.target.get_hp() < initial_target_hp}"
        ),
        f"economy: actions={refreshed.action_economy.actions}, adjacent={adjacent}",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "fighter: start=(2, 2), end=(6, 2), target=Decision Hero",
        "target hp: before=10, after=5, damaged=True",
        "economy: actions=0, adjacent=True",
    ]
    assert scene.agent_actor.position != initial_position
    assert scene.target.get_hp() < initial_target_hp
    assert readout_lines == expected_lines


def test_move_and_attack_composite_reports_steps() -> None:
    """MoveAndAttack chains movement, refresh, and attack into one result."""
    scene = create_decision_scene(target_position=(5, 2))
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_target_hp = scene.target.get_hp()
    try:
        with fixed_dice_faces(3, 3, 3, 3):
            result = MoveAndAttack(str(scene.target.uuid)).execute(
                interface,
                state,
                str(scene.agent_actor.uuid),
            )
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    adjacent = max(
        abs(scene.agent_actor.position[0] - scene.target.position[0]),
        abs(scene.agent_actor.position[1] - scene.target.position[1]),
    ) == 1
    readout_lines = [
        (
            f"composite: success={result.success}, "
            f"actions_taken={result.actions_taken}, description={result.description}"
        ),
        (
            f"positions: actor={scene.agent_actor.position}, "
            f"target={scene.target.position}, adjacent={adjacent}"
        ),
        f"target hp: before={initial_target_hp}, after={scene.target.get_hp()}",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "composite: success=True, actions_taken=2, description=Moved and attacked",
        "positions: actor=(4, 2), target=(5, 2), adjacent=True",
        "target hp: before=10, after=5",
    ]
    assert result.success
    assert readout_lines == expected_lines


def test_interrupt_detection_compares_before_result_and_after_state() -> None:
    """Interrupt detection identifies important changes between snapshots."""
    scene = create_decision_scene()
    interface = LocalGameInterface()
    before = interface.get_tactical_state(str(scene.agent_actor.uuid))
    new_enemy = TacticalEntity(
        uuid=str(uuid4()),
        name="New Threat",
        position=(6, 2),
        hp=5,
        max_hp=5,
        ac=12,
        distance_feet=20,
        faction="heroes",
    )
    after = before.model_copy(
        update={
            "me": before.me.model_copy(update={"conditions": ["Poisoned"]}),
            "enemies": [*before.enemies, new_enemy],
        }
    )
    result = ActionResult(
        success=True,
        entity_hp=before.me.hp - 1,
        deaths=[scene.target.name],
    )

    interrupts = detect_interrupts(before, result, after)

    readout_lines = [
        f"interrupts: {[interrupt.value for interrupt in interrupts]}",
        (
            f"state change: hp={before.me.hp}->{result.entity_hp}, "
            f"enemies={len(before.enemies)}->{len(after.enemies)}, "
            f"conditions={after.me.conditions}"
        ),
        f"death notice: {result.deaths}",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "interrupts: ['damage_taken', 'target_died', 'new_enemy', 'condition']",
        "state change: hp=17->16, enemies=1->2, conditions=['Poisoned']",
        "death notice: ['Decision Hero']",
    ]
    assert InterruptType.DAMAGE_TAKEN in interrupts
    assert readout_lines == expected_lines


def test_utility_ai_scores_damage_and_focus_fire() -> None:
    """UtilityAI ranks action-target pairs with weighted scorer breakdowns."""
    scene = create_two_target_scene()
    interface = LocalGameInterface()
    state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    utility = UtilityAI([
        DamageScorer(weight=1.0),
        FocusFireScorer(weight=0.5),
    ])

    ranked = utility.evaluate_all(state)
    best = utility.pick_best(state)

    runner_up = ranked[1]
    readout_lines = [
        (
            f"utility: options={len(ranked)}, best={best.target.target_name}, "
            f"score={best.score:.2f}"
        ),
        (
            f"best breakdown: damage={best.breakdown['damage']:.2f}, "
            f"focus_fire={best.breakdown['focus_fire']:.2f}"
        ),
        f"runner-up: target={runner_up.target.target_name}, score={runner_up.score:.2f}",
        (
            f"weakest: {state.weakest_enemy().name}, "
            f"sturdy_attack={state.find_attack_targeting(str(scene.sturdy_target.uuid)) is not None}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "utility: options=104, best=Wounded Hero, score=10.40",
        "best breakdown: damage=5.40, focus_fire=5.00",
        "runner-up: target=Sturdy Hero, score=5.40",
        "weakest: Wounded Hero, sturdy_attack=True",
    ]
    assert best == ranked[0]
    assert readout_lines == expected_lines


def test_utility_agent_executes_the_best_scored_option() -> None:
    """UtilityAgent refreshes state and executes the highest-scoring option."""
    scene = create_two_target_scene()
    interface = LocalGameInterface()
    utility = UtilityAI([
        DamageScorer(weight=1.0),
        FocusFireScorer(weight=0.5),
    ])
    pre_state = interface.get_tactical_state(str(scene.agent_actor.uuid))
    chosen = utility.pick_best(pre_state)
    agent = UtilityAgent(interface, str(scene.agent_actor.uuid), utility)
    modifier_uuid = make_melee_attack_auto_hit(scene.agent_actor)
    initial_weak_hp = scene.weak_target.get_hp()
    initial_sturdy_hp = scene.sturdy_target.get_hp()
    try:
        with fixed_dice_faces(3, 3, 3, 3):
            agent.run_turn()
    finally:
        clear_melee_attack_modifier(scene.agent_actor, modifier_uuid)

    refreshed = interface.get_tactical_state(str(scene.agent_actor.uuid))
    readout_lines = [
        f"agent choice: target={chosen.target.target_name}, score={chosen.score:.2f}",
        (
            f"weak target hp: before={initial_weak_hp}, "
            f"after={scene.weak_target.get_hp()}, "
            f"damaged={scene.weak_target.get_hp() < initial_weak_hp}"
        ),
        (
            f"sturdy target hp: before={initial_sturdy_hp}, "
            f"after={scene.sturdy_target.get_hp()}, "
            f"unchanged={scene.sturdy_target.get_hp() == initial_sturdy_hp}"
        ),
        (
            f"economy: actions={refreshed.action_economy.actions}, "
            f"scorers={[type(scorer).__name__ for scorer in utility.scorers]}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "agent choice: target=Wounded Hero, score=10.40",
        "weak target hp: before=7, after=2, damaged=True",
        "sturdy target hp: before=10, after=10, unchanged=True",
        "economy: actions=0, scorers=['DamageScorer', 'FocusFireScorer']",
    ]
    assert chosen is not None
    assert readout_lines == expected_lines
