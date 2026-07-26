"""Tutorial tests for action templates, discovery, target indices, and costs."""

from typing import cast
from uuid import uuid4

from pytest import MonkeyPatch, mark

from dnd.actions import (
    Attack,
    Dash,
    Jump,
    MovementEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.actions_functional import (
    apply_action_overrides,
    clear_action_overrides,
    execute_by_index,
    get_available_actions,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_actions import ActionCategory, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.base_object import BaseObject
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items.consumables import HEALING_POTION_RECIPE
from dnd.items.spell_items import fireball_scroll_recipe, fire_bolt_scroll_recipe
from dnd.items.test_reactions import PrepareIntercept
from dnd.items.weapons import CLUB_RECIPE
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.spells.evocation import Fireball
from dnd.spells.conjuration import MistyStep


def reset_action_state() -> None:
    """Clear global state and create the tutorial arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 20, 20)


def create_tutorial_actor(
    name: str = "Hero",
    position: tuple[int, int] = (2, 2),
    faction: str | None = "heroes",
    *,
    standard_actions: bool = True,
) -> Entity:
    """Create a deterministic actor for action-system examples."""
    actor_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
            ]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    actor = Entity.create(source_entity_uuid=actor_id, name=name, config=config)
    if standard_actions:
        setup_standard_actions(actor)
    return actor


def find_action(actions, template_name: str):
    """Find one available-action row by template name."""
    for info in actions.all_actions:
        if info.template_name == template_name:
            return info
    raise AssertionError(
        f"{template_name!r} not found in {[info.template_name for info in actions.all_actions]}"
    )


def find_attack_action(actions):
    """Find the first entity-targeting attack row."""
    for info in actions.entity_actions:
        if info.is_attack:
            return info
    raise AssertionError("No attack action found")


def entity_target_name(target) -> str:
    """Resolve one entity-target row without accepting optional identity."""
    assert target.target_uuid is not None
    entity = Entity.get(target.target_uuid)
    assert entity is not None
    return entity.name


def deny_nonreaction_actions(actor: Entity) -> None:
    """Set the neutral action-permission gate to zero for discovery tests."""
    actor.action_economy.action_permission.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            name="Discovery permission denied",
            value=-1,
        )
    )
    assert actor.can_take_actions() is False


def unexpected_discovery_work(*args: object, **kwargs: object) -> None:
    """Fail when an unaffordable collector performs target-specific work."""
    del args, kwargs
    raise AssertionError("unaffordable action performed target discovery")


def test_first_action_example_prints_visible_turn_menu(capsys) -> None:
    """One actor prints grouped choices, target previews, and paid Dash state."""
    reset_action_state()
    hero = create_goblin(name="Scout", position=(5, 5), faction="heroes")
    create_skeleton(name="Skeleton", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses()

    available = get_available_actions(hero)
    entity_names = {
        info.template_name for info in available.entity_actions
    }
    assert "Shove" in entity_names
    dash_info = next(
        info for info in available.self_actions if info.template_name == "Dash"
    )
    move_info = next(
        info for info in available.position_actions if info.template_name == "Move"
    )
    attack_info = next(info for info in available.entity_actions if info.is_attack)
    move_target = move_info.valid_targets[0]
    attack_target = attack_info.valid_targets[0]
    assert attack_target.target_uuid is not None
    attack_target_entity = Entity.get(attack_target.target_uuid)
    assert attack_target_entity is not None

    readout_lines = [
        f"actor: {hero.name}",
        f"movement left: {available.remaining_movement}",
        (
            "groups: "
            f"entity={len(available.entity_actions)}, "
            f"position={len(available.position_actions)}, "
            f"self={len(available.self_actions)}, "
            f"object={len(available.object_actions)}"
        ),
        (
            "dash row: "
            f"target={dash_info.target_type.value}, "
            f"cost={dash_info.cost_amount} {dash_info.cost_type}, "
            f"afford={dash_info.can_afford}"
        ),
        (
            "move row: "
            f"target {move_target.index} -> {move_target.position}, "
            f"distance={move_target.distance}, path={move_target.path}"
        ),
        (
            "attack row: "
            f"{attack_info.weapon_name} -> {attack_target_entity.name}, "
            f"distance={attack_target.distance}"
        ),
    ]

    result = execute_by_index(hero, dash_info.template_name, 0, available=available)
    assert result is not None
    after = get_available_actions(hero)
    dash_after = next(info for info in after.self_actions if info.template_name == "Dash")
    readout_lines.extend(
        [
            f"dash result canceled: {result.canceled}",
            f"actions after dash: {hero.action_economy.actions.normalized_score}",
            f"dash affordable after dash: {dash_after.can_afford}",
        ]
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "actor: Scout",
        "movement left: 30",
        "groups: entity=4, position=3, self=7, object=0",
        "dash row: target=self, cost=1 actions, afford=True",
        "move row: target 0 -> (5, 6), distance=5, path=[(5, 5), (5, 6)]",
        "attack row: Scimitar -> Skeleton, distance=5",
        "dash result canceled: False",
        "actions after dash: 0",
        "dash affordable after dash: False",
    ]
    assert readout_lines == expected_lines
    assert "Dashing" in hero.active_conditions
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_action_templates_instantiate_into_executable_actions(capsys) -> None:
    """Registered actions are templates; executable actions are one-shot copies."""
    reset_action_state()
    actor = create_tutorial_actor(standard_actions=False)

    non_template = Dash(source_entity_uuid=actor.uuid, template=False)
    non_template_rejected = False
    try:
        actor.register_action(non_template)
    except ValueError as exc:
        assert "template" in str(exc)
        non_template_rejected = True
    else:
        raise AssertionError("register_action accepted a non-template action")

    template = Dash(source_entity_uuid=actor.uuid, template=True)
    actor.register_action(template)
    assert actor.get_action_template("Dash") is template

    template_apply_rejected = False
    try:
        template.apply()
    except ValueError as exc:
        assert "Cannot apply template" in str(exc)
        template_apply_rejected = True
    else:
        raise AssertionError("template.apply() did not raise")

    instance = template.instantiate()
    assert instance.template is False
    assert instance.uuid != template.uuid
    assert instance.source_entity_uuid == template.source_entity_uuid
    assert instance.use_register is False

    template_lines = [
        f"non-template rejected: {non_template_rejected}",
        f"template lookup: {actor.get_action_template('Dash') is template}",
        f"template apply rejected: {template_apply_rejected}",
        f"instance template flag: {instance.template}",
        f"instance has fresh uuid: {instance.uuid != template.uuid}",
        f"instance source copied: {instance.source_entity_uuid == template.source_entity_uuid}",
        f"instance use_register: {instance.use_register}",
    ]

    print("\n".join(template_lines))

    expected_template_lines = [
        "non-template rejected: True",
        "template lookup: True",
        "template apply rejected: True",
        "instance template flag: False",
        "instance has fresh uuid: True",
        "instance source copied: True",
        "instance use_register: False",
    ]
    assert template_lines == expected_template_lines
    assert capsys.readouterr().out.splitlines() == expected_template_lines


def test_standard_action_discovery_groups_choices_for_clients(capsys) -> None:
    """Available actions are grouped into entity, position, self, and object rows."""
    reset_action_state()
    hero = create_goblin(name="Scout", position=(5, 5), faction="heroes")
    skeleton = create_skeleton(name="Skeleton", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses()

    available = get_available_actions(hero)
    self_names = {info.template_name for info in available.self_actions}
    position_names = {info.template_name for info in available.position_actions}
    entity_names = {info.template_name for info in available.entity_actions}

    assert available.entity_uuid == hero.uuid
    assert available.remaining_movement == hero.action_economy.movement.normalized_score
    assert {"Dash", "Dodge", "Disengage"}.issubset(self_names)
    assert "Move" in position_names
    assert "Jump" in position_names
    assert "Shove" in entity_names

    dash_info = find_action(available, "Dash")
    assert dash_info.target_type == TargetType.SELF
    assert dash_info.valid_targets[0].index == 0
    assert dash_info.cost_type == "actions"
    assert dash_info.cost_amount == 1
    assert dash_info.can_afford is True

    move_info = find_action(available, "Move")
    assert move_info.target_type == TargetType.POSITION_PATH
    assert move_info.action_category == ActionCategory.MOVEMENT
    assert move_info.valid_targets[0].position is not None
    assert move_info.valid_targets[0].path is not None

    attack_info = find_attack_action(available)
    assert attack_info.action_category == ActionCategory.ATTACK
    assert attack_info.weapon_slot is not None
    assert attack_info.weapon_name is not None
    assert any(target.target_uuid == skeleton.uuid for target in attack_info.valid_targets)

    assert available.all_actions == (
        available.entity_actions
        + available.position_actions
        + available.self_actions
        + available.object_actions
    )

    move_target = move_info.valid_targets[0]
    attack_names = [
        entity_target_name(target) for target in attack_info.valid_targets
    ]
    discovery_lines = [
        f"entity uuid matches actor: {available.entity_uuid == hero.uuid}",
        f"remaining movement: {available.remaining_movement}",
        (
            "groups: "
            f"entity={len(available.entity_actions)}, "
            f"position={len(available.position_actions)}, "
            f"self={len(available.self_actions)}, "
            f"object={len(available.object_actions)}"
        ),
        f"self actions include: {sorted(name for name in self_names if name in {'Dash', 'Dodge', 'Disengage'})}",
        (
            "dash row: "
            f"target={dash_info.target_type.value}, index={dash_info.valid_targets[0].index}, "
            f"cost={dash_info.cost_amount} {dash_info.cost_type}, afford={dash_info.can_afford}"
        ),
        (
            "move row: "
            f"category={move_info.action_category.value}, "
            f"target={move_target.position}, path={move_target.path}"
        ),
        f"attack row: weapon={attack_info.weapon_name}, targets={attack_names}",
        f"all actions ordered: {available.all_actions == available.entity_actions + available.position_actions + available.self_actions + available.object_actions}",
    ]

    print("\n".join(discovery_lines))

    expected_discovery_lines = [
        "entity uuid matches actor: True",
        "remaining movement: 30",
        "groups: entity=4, position=3, self=7, object=0",
        "self actions include: ['Dash', 'Disengage', 'Dodge']",
        "dash row: target=self, index=0, cost=1 actions, afford=True",
        "move row: category=movement, target=(5, 6), path=[(5, 5), (5, 6)]",
        "attack row: weapon=Scimitar, targets=['Skeleton']",
        "all actions ordered: True",
    ]
    assert discovery_lines == expected_discovery_lines
    assert capsys.readouterr().out.splitlines() == expected_discovery_lines


def test_authored_entity_action_remains_without_targets_when_cost_is_exhausted() -> None:
    """Default discovery keeps identity while short-circuiting target work."""
    reset_action_state()
    hero = create_goblin(name="Spent Hero", position=(5, 5), faction="heroes")
    enemy = create_skeleton(
        name="Still Valid Target",
        position=(6, 5),
        faction="monsters",
    )
    Entity.update_all_entities_senses()
    hero.action_economy.consume("actions", 1)

    attack = find_attack_action(get_available_actions(hero))

    assert attack.can_afford is False
    assert attack.valid_targets == []
    assert enemy.uuid in hero.senses.entities


def test_affordable_authored_entity_action_remains_with_no_valid_targets() -> None:
    """An authored targeted action remains discoverable before a target exists."""
    reset_action_state()
    hero = create_goblin(name="Lonely Hero", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    attack = find_attack_action(get_available_actions(hero))

    assert attack.can_afford is True
    assert attack.valid_targets == []


def test_affordable_self_action_remains_when_its_rule_prerequisite_fails() -> None:
    """Self-action identity remains visible while its prerequisite disables it."""
    reset_action_state()
    hero = create_goblin(name="Unfocused Hero", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    drop_concentration = find_action(
        get_available_actions(hero),
        "Drop Concentration",
    )

    assert drop_concentration.can_afford is True
    assert drop_concentration.valid_targets == []


def test_legal_only_action_discovery_omits_cost_and_requirement_blockers() -> None:
    """The controller view remains sparse when an action cannot execute now."""
    reset_action_state()
    hero = create_goblin(name="Blocked Hero", position=(5, 5), faction="heroes")
    enemy = create_skeleton(
        name="Visible Target",
        position=(6, 5),
        faction="monsters",
    )
    Entity.update_all_entities_senses()
    hero.action_economy.consume("actions", 1)

    authored = get_available_actions(hero)
    legal = get_available_actions(hero, legal_only=True)

    authored_attack = find_attack_action(authored)
    assert authored_attack.can_afford is False
    assert authored_attack.valid_targets == []
    assert enemy.uuid in hero.senses.entities
    assert find_action(authored, "Drop Concentration").valid_targets == []
    assert not any(action.is_attack for action in legal.entity_actions)
    assert not any(
        action.template_name == "Drop Concentration"
        for action in legal.self_actions
    )


def test_contextual_object_and_environment_discovery_remains_sparse() -> None:
    """Invalid contextual affordances do not become authored disabled rows."""
    reset_action_state()
    hero = create_tutorial_actor(position=(3, 3))
    distant_potion = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    distant_potion.place_on_grid((5, 3))
    Entity.update_all_entities_senses()

    available = get_available_actions(hero)

    assert not any(
        action.template_name in {"Pick Up", "Attack Object"}
        for action in available.object_actions
    )
    assert not any(
        action.source_item_uuid == distant_potion.uuid
        for action in available.all_actions
    )


def test_unaffordable_authored_position_and_object_paths_do_no_target_work(
    monkeypatch: MonkeyPatch,
) -> None:
    """Disabled authored rows survive without path, LOS, or object validation."""
    reset_action_state()
    hero = create_tutorial_actor(position=(3, 3))
    club = materialize_item(
        CLUB_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    club.place_on_grid((4, 3))
    Entity.update_all_entities_senses()
    jump = hero.get_action_template("Jump")
    assert isinstance(jump, Jump)
    monkeypatch.setattr(jump, "position_discovery", None)
    monkeypatch.setattr(
        Entity,
        "_collect_fast_move_targets",
        unexpected_discovery_work,
    )
    monkeypatch.setattr(Jump, "get_valid_positions", unexpected_discovery_work)
    monkeypatch.setattr(BaseAction, "pre_validate", unexpected_discovery_work)
    deny_nonreaction_actions(hero)

    authored = get_available_actions(hero)
    legal = get_available_actions(hero, legal_only=True)

    for template_name in ("Move", "Jump"):
        row = find_action(authored, template_name)
        assert row.can_afford is False
        assert row.valid_targets == []
        assert not any(
            candidate.template_name == template_name
            for candidate in legal.position_actions
        )
    assert authored.object_actions == []
    assert legal.object_actions == []


@mark.parametrize("template_name", ["Jump", "Prepare Intercept"])
def test_position_action_rows_report_no_rules_valid_targets(
    template_name: str,
) -> None:
    """An authored position action remains visible when no destination exists."""
    reset_action_state()
    GridMap.reset()
    get_map().create_rectangle(2, 2, 1, 1)
    actor = create_tutorial_actor(position=(2, 2))
    if template_name == "Prepare Intercept":
        actor.register_action(
            PrepareIntercept(
                source_entity_uuid=actor.uuid,
                template=True,
            )
        )
    Entity.update_all_entities_senses()

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    row = find_action(authored, template_name)
    assert row.can_afford is True
    assert row.availability_status == "no_valid_targets"
    assert row.valid_targets == []
    assert not any(
        candidate.template_name == template_name
        for candidate in legal.position_actions
    )


@mark.parametrize("template_name", ["Jump", "Prepare Intercept"])
def test_position_action_rows_report_target_cost_unaffordable(
    template_name: str,
) -> None:
    """Rules-valid destinations blocked only by movement get an exact status."""
    reset_action_state()
    actor = create_tutorial_actor(position=(2, 2))
    if template_name == "Prepare Intercept":
        actor.register_action(
            PrepareIntercept(
                source_entity_uuid=actor.uuid,
                template=True,
            )
        )
    Entity.update_all_entities_senses()
    template = actor.get_action_template(template_name)
    assert template is not None
    template.set_target_position((3, 2))
    actor.action_economy.consume(
        "movement",
        actor.action_economy.movement.normalized_score,
    )

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    row = find_action(authored, template_name)
    assert row.can_afford is True
    assert row.availability_status == "target_cost_unaffordable"
    assert row.valid_targets == []
    assert [(cost.cost_type, cost.cost) for cost in row.costs] == [
        (
            "bonus_actions"
            if template_name == "Jump"
            else "actions",
            1,
        )
    ]
    assert not any(
        candidate.template_name == template_name
        for candidate in legal.position_actions
    )


def test_entity_action_discovery_does_not_retain_candidate_targets() -> None:
    """Discovery validates target-specialized copies, never live templates."""
    reset_action_state()
    actor = create_tutorial_actor(position=(2, 2))
    create_skeleton(name="First Target", position=(3, 2), faction="monsters")
    create_skeleton(name="Second Target", position=(2, 3), faction="monsters")
    Entity.update_all_entities_senses()
    shake_awake = actor.get_action_template("Shake Awake")
    shove = actor.get_action_template("Shove")
    assert shake_awake is not None
    assert shove is not None
    assert shake_awake.target_entity_uuid is None
    assert shove.target_entity_uuid is None

    get_available_actions(actor)

    assert shake_awake.target_entity_uuid is None
    assert shove.target_entity_uuid is None


def test_move_row_reports_no_rules_valid_routes() -> None:
    """A map with no destination keeps the authored Move row with exact status."""
    reset_action_state()
    GridMap.reset()
    get_map().create_rectangle(2, 2, 1, 1)
    actor = create_tutorial_actor(position=(2, 2))
    Entity.update_all_entities_senses()

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    move = find_action(authored, "Move")
    assert move.can_afford is True
    assert move.availability_status == "no_valid_targets"
    assert move.valid_targets == []
    assert not any(
        candidate.template_name == "Move"
        for candidate in legal.position_actions
    )


def test_move_row_reports_movement_budget_exhaustion() -> None:
    """Rules-valid routes blocked only by movement retain a typed authored row."""
    reset_action_state()
    actor = create_tutorial_actor(position=(2, 2))
    Entity.update_all_entities_senses()
    actor.action_economy.consume(
        "movement",
        actor.action_economy.movement.normalized_score,
    )

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    move = find_action(authored, "Move")
    assert move.can_afford is True
    assert move.availability_status == "target_cost_unaffordable"
    assert move.valid_targets == []
    assert move.costs == []
    assert not any(
        candidate.template_name == "Move"
        for candidate in legal.position_actions
    )


def test_generic_position_row_reports_requirements_not_target_cost(
    monkeypatch: MonkeyPatch,
) -> None:
    """A rules-invalid position is not mislabeled target-cost unaffordable."""
    reset_action_state()
    actor = create_tutorial_actor(position=(2, 2))
    actor.action_economy.spell_slot_2.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            name="Misty Step regression slot",
            value=1,
        )
    )
    actor.register_action(
        MistyStep(
            source_entity_uuid=actor.uuid,
            template=True,
        )
    )
    Entity.update_all_entities_senses()
    monkeypatch.setattr(
        MistyStep,
        "validate_requirements_for_discovery",
        lambda self: False,
    )

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    misty_step = next(
        action
        for action in authored.position_actions
        if action.base_template_name == "Misty Step"
    )
    assert misty_step.can_afford is True
    assert misty_step.availability_status == "no_valid_targets"
    assert misty_step.valid_targets == []
    assert not any(
        candidate.base_template_name == "Misty Step"
        for candidate in legal.position_actions
    )


def test_entity_row_reports_target_cost_unaffordable(
    monkeypatch: MonkeyPatch,
) -> None:
    """A rules-valid enemy blocked only by target cost gets the exact status."""
    reset_action_state()
    actor = create_goblin(
        name="Cost-bound Attacker",
        position=(2, 2),
        faction="heroes",
    )
    create_skeleton(name="Adjacent Enemy", position=(3, 2), faction="monsters")
    Entity.update_all_entities_senses()

    def impossible_target_cost(self: Attack) -> list[Cost]:
        return [
            Cost(
                name="Impossible target movement",
                cost_type="movement",
                cost=999,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]

    monkeypatch.setattr(
        Attack,
        "get_target_dynamic_costs",
        impossible_target_cost,
    )

    authored = get_available_actions(actor)
    legal = get_available_actions(actor, legal_only=True)

    attack = find_attack_action(authored)
    assert attack.can_afford is True
    assert attack.availability_status == "target_cost_unaffordable"
    assert attack.valid_targets == []
    assert all(cost.cost_type != "movement" for cost in attack.costs)
    assert not any(candidate.is_attack for candidate in legal.entity_actions)


def test_unaffordable_contextual_self_item_stays_sparse_without_validation(
    monkeypatch: MonkeyPatch,
) -> None:
    """A disabled self-use item does not run its action prerequisite."""
    reset_action_state()
    hero = create_tutorial_actor(position=(3, 3))
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert hero.loot_item(potion)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(BaseAction, "pre_validate", unexpected_discovery_work)
    deny_nonreaction_actions(hero)

    for legal_only in (False, True):
        available = get_available_actions(hero, legal_only=legal_only)
        assert not any(
            action.source_item_uuid == potion.uuid
            for action in available.all_actions
        )


def test_unaffordable_contextual_entity_item_avoids_target_pool_work(
    monkeypatch: MonkeyPatch,
) -> None:
    """A disabled entity-target scroll is omitted before target enumeration."""
    reset_action_state()
    hero = create_tutorial_actor(position=(3, 3))
    scroll = materialize_item(
        fire_bolt_scroll_recipe(caster_level=5),
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert hero.loot_item(scroll)
    create_skeleton(name="Scroll Target", position=(4, 3), faction="monsters")
    Entity.update_all_entities_senses()
    monkeypatch.setattr(Entity, "_compute_target_pool", unexpected_discovery_work)
    deny_nonreaction_actions(hero)

    for legal_only in (False, True):
        available = get_available_actions(hero, legal_only=legal_only)
        assert not any(
            action.source_item_uuid == scroll.uuid
            for action in available.all_actions
        )


def test_unaffordable_contextual_aoe_item_avoids_position_preview_work(
    monkeypatch: MonkeyPatch,
) -> None:
    """A disabled AoE scroll is omitted before position enumeration."""
    reset_action_state()
    hero = create_tutorial_actor(position=(3, 3))
    scroll = materialize_item(
        fireball_scroll_recipe(cast_level=3),
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert hero.loot_item(scroll)
    create_skeleton(name="Blast Target", position=(5, 3), faction="monsters")
    Entity.update_all_entities_senses()
    monkeypatch.setattr(Fireball, "get_valid_positions", unexpected_discovery_work)
    monkeypatch.setattr(
        Entity,
        "_compute_aoe_at_position",
        unexpected_discovery_work,
    )
    deny_nonreaction_actions(hero)

    for legal_only in (False, True):
        available = get_available_actions(hero, legal_only=legal_only)
        assert not any(
            action.source_item_uuid == scroll.uuid
            for action in available.all_actions
        )


def test_execute_by_index_instantiates_and_pays_costs(capsys) -> None:
    """A controller can execute a discovered row by template name and target index."""
    reset_action_state()
    actor = create_tutorial_actor()
    available = get_available_actions(actor)
    dash_info = find_action(available, "Dash")

    result = execute_by_index(actor, dash_info.template_name, 0, available=available)

    assert result is not None
    assert not result.canceled
    assert "Dashing" in actor.active_conditions
    assert actor.action_economy.actions.normalized_score == 0

    after = get_available_actions(actor)
    dash_after = find_action(after, "Dash")
    assert dash_after.can_afford is False
    assert dash_after.valid_targets == []

    execute_lines = [
        f"dash target index: {dash_info.valid_targets[0].index}",
        f"result canceled: {result.canceled}",
        f"dashing condition active: {'Dashing' in actor.active_conditions}",
        f"actions after dash: {actor.action_economy.actions.normalized_score}",
        f"dash affordable after dash: {dash_after.can_afford}",
        f"dash targets after dash: {len(dash_after.valid_targets)}",
    ]

    print("\n".join(execute_lines))

    expected_execute_lines = [
        "dash target index: 0",
        "result canceled: False",
        "dashing condition active: True",
        "actions after dash: 0",
        "dash affordable after dash: False",
        "dash targets after dash: 0",
    ]
    assert execute_lines == expected_execute_lines
    assert capsys.readouterr().out.splitlines() == expected_execute_lines


def test_dash_adds_current_speed_after_speed_bonuses_and_movement_spending() -> None:
    """Dash adds speed, not base speed, remaining movement, or prior Dash budget."""
    reset_action_state()
    actor = create_tutorial_actor()
    movement = actor.action_economy.movement
    movement.self_static.add_value_modifier(NumericalModifier(
        name="Fast Movement",
        value=10,
        source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid,
    ))
    movement.self_static.add_value_modifier(NumericalModifier(
        name="movement cost",
        value=-15,
        source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid,
    ))
    available = get_available_actions(actor)
    dash_info = find_action(available, "Dash")

    result = execute_by_index(actor, dash_info.template_name, 0, available=available)

    assert result is not None
    assert result.canceled is False
    assert actor.action_economy.current_speed() == 40
    assert movement.normalized_score == 65
    dashing_modifiers = [
        modifier
        for modifier in movement.self_static.value_modifiers.values()
        if modifier.name == "Dashing"
    ]
    assert [modifier.value for modifier in dashing_modifiers] == [40]


def test_floor_and_inventory_item_actions_are_discovered_and_routed(capsys) -> None:
    """Object and item-use actions appear through the same discovery result."""
    reset_action_state()
    actor = create_tutorial_actor(position=(3, 3))
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    potion.place_on_grid((4, 3))
    Entity.update_all_entities_senses()

    available = get_available_actions(actor)
    pickup_info = find_action(available, "Pick Up")
    potion_target = next(
        target for target in pickup_info.valid_targets if target.target_uuid == potion.uuid
    )

    assert pickup_info.target_type == TargetType.OBJECT
    assert pickup_info.cost_amount == 0
    assert potion_target.distance == 5

    pickup_result = execute_by_index(
        actor,
        "Pick Up",
        potion_target.index,
        available=available,
    )

    assert pickup_result is not None
    assert not pickup_result.canceled
    assert potion.uuid in actor.inventory.items
    assert get_map().get_object_position(potion.uuid) is None
    potion_in_inventory_after_pickup = potion.uuid in actor.inventory.items
    potion_map_position_after_pickup = get_map().get_object_position(potion.uuid)

    available = get_available_actions(actor)
    drink_info = next(
        info
        for info in available.self_actions
        if info.is_item_use and info.source_item_uuid == potion.uuid
    )

    assert drink_info.template_name.startswith("Drink Potion__item_")
    assert drink_info.display_name == "Drink Potion (Potion of Healing)"
    assert drink_info.valid_targets[0].index == 0
    assert drink_info.cost_type == "bonus_actions"
    assert drink_info.cost_amount == 1
    assert drink_info.item_charge_cost == 1
    assert drink_info.fixed_healing == 7

    bonus_actions_before_drink = actor.action_economy.bonus_actions.normalized_score

    drink_result = execute_by_index(
        actor,
        drink_info.template_name,
        0,
        available=available,
    )

    assert drink_result is not None
    assert not drink_result.canceled
    assert bonus_actions_before_drink == 1
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert potion.uuid not in actor.inventory.items
    assert BaseBlock.get(potion.uuid) is None

    item_lines = [
        (
            "pickup row: "
            f"target={pickup_info.target_type.value}, cost={pickup_info.cost_amount}, "
            f"distance={potion_target.distance}"
        ),
        f"pickup canceled: {pickup_result.canceled}",
        f"potion in inventory after pickup: {potion_in_inventory_after_pickup}",
        f"potion map position after pickup: {potion_map_position_after_pickup}",
        f"drink row: {drink_info.display_name}, target index={drink_info.valid_targets[0].index}",
        f"drink canceled: {drink_result.canceled}",
        f"potion in inventory after drink: {potion.uuid in actor.inventory.items}",
        f"potion block exists after drink: {BaseBlock.get(potion.uuid) is not None}",
    ]

    print("\n".join(item_lines))

    expected_item_lines = [
        "pickup row: target=object, cost=0, distance=5",
        "pickup canceled: False",
        "potion in inventory after pickup: True",
        "potion map position after pickup: None",
        "drink row: Drink Potion (Potion of Healing), target index=0",
        "drink canceled: False",
        "potion in inventory after drink: False",
        "potion block exists after drink: False",
    ]
    assert item_lines == expected_item_lines
    assert capsys.readouterr().out.splitlines() == expected_item_lines


def test_item_bound_spell_consumes_its_charge_before_action_completion() -> None:
    """Specialized spell events retain the canonical finite-item child lineage."""
    reset_action_state()
    actor = create_tutorial_actor(position=(2, 2))
    target = create_skeleton(
        name="Scroll Target",
        position=(4, 2),
        faction="monsters",
    )
    scroll = materialize_item(
        fire_bolt_scroll_recipe(caster_level=5),
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert actor.loot_item(scroll)
    Entity.update_all_entities_senses(max_distance=20)
    available = get_available_actions(actor)
    row = next(
        info
        for info in available.entity_actions
        if info.source_item_uuid == scroll.uuid
    )
    target_row = next(
        option
        for option in row.valid_targets
        if option.target_uuid == target.uuid
    )

    result = execute_by_index(
        actor,
        row.template_name,
        target_row.index,
        available=available,
    )

    assert result is not None and not result.canceled
    assert BaseBlock.get(scroll.uuid) is None
    charge_events = EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
    assert [event.phase for event in charge_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    completion = charge_events[-1]
    assert isinstance(completion, ItemChargeConsumptionEvent)
    assert completion.parent_lineage == result.lineage_uuid
    assert completion.lineage_uuid in result.children_lineages


def test_action_overrides_change_discovery_and_consumed_costs(capsys) -> None:
    """Temporary action overrides affect both display and execution."""
    reset_action_state()
    actor = create_tutorial_actor()
    dash_template = actor.get_action_template("Dash")
    assert dash_template is not None

    modified = apply_action_overrides(
        actor,
        lambda action: action.name == "Dash",
        {"alt_cost_type": "bonus_actions"},
    )
    assert dash_template.uuid in modified

    available = get_available_actions(actor)
    dash_info = find_action(available, "Dash")
    assert dash_info.cost_type == "bonus_actions"

    result = execute_by_index(actor, "Dash", 0, available=available)

    assert result is not None
    assert not result.canceled
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.bonus_actions.normalized_score == 0

    clear_action_overrides(actor, modified)
    assert dash_template.alt_cost_type is None

    override_lines = [
        f"dash override applied: {dash_template.uuid in modified}",
        f"displayed cost type: {dash_info.cost_type}",
        f"result canceled: {result.canceled}",
        f"actions after dash: {actor.action_economy.actions.normalized_score}",
        f"bonus actions after dash: {actor.action_economy.bonus_actions.normalized_score}",
        f"override cleared: {dash_template.alt_cost_type is None}",
    ]

    print("\n".join(override_lines))

    expected_override_lines = [
        "dash override applied: True",
        "displayed cost type: bonus_actions",
        "result canceled: False",
        "actions after dash: 1",
        "bonus actions after dash: 0",
        "override cleared: True",
    ]
    assert override_lines == expected_override_lines
    assert capsys.readouterr().out.splitlines() == expected_override_lines


def test_target_filters_shape_entity_target_pools(capsys) -> None:
    """Discovery can narrow entity targets by relationship and death state."""
    reset_action_state()
    hero = create_goblin(name="Hero", position=(5, 5), faction="heroes")
    ally = create_goblin(name="Ally", position=(5, 6), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")
    dead_enemy = create_skeleton(name="Dead Enemy", position=(6, 6), faction="monsters")
    dead_enemy.health.take_damage(999, DamageType.BLUDGEONING, hero.uuid)
    Entity.update_all_entities_senses()

    default_attack = find_attack_action(hero.get_available_actions())
    assert [target.target_uuid for target in default_attack.valid_targets] == [enemy.uuid]
    default_names = [
        entity_target_name(target) for target in default_attack.valid_targets
    ]

    ally_attack = find_attack_action(hero.get_available_actions(target_filter="allies"))
    assert [target.target_uuid for target in ally_attack.valid_targets] == [ally.uuid]
    ally_names = [
        entity_target_name(target) for target in ally_attack.valid_targets
    ]

    all_targets_attack = find_attack_action(
        hero.get_available_actions(target_filter="all", include_dead=True)
    )
    assert [target.target_uuid for target in all_targets_attack.valid_targets] == [
        enemy.uuid,
        dead_enemy.uuid,
        ally.uuid,
    ]
    all_names = [
        entity_target_name(target) for target in all_targets_attack.valid_targets
    ]

    target_lines = [
        f"default targets: {default_names}",
        f"ally targets: {ally_names}",
        f"all targets with dead included: {all_names}",
    ]

    print("\n".join(target_lines))

    expected_target_lines = [
        "default targets: ['Enemy']",
        "ally targets: ['Ally']",
        "all targets with dead included: ['Enemy', 'Dead Enemy', 'Ally']",
    ]
    assert target_lines == expected_target_lines
    assert capsys.readouterr().out.splitlines() == expected_target_lines


def test_safe_movement_metadata_shapes_path_choice(capsys) -> None:
    """Discovery exposes hazardous paths and safe alternatives."""
    reset_action_state()

    grid = get_map()
    hazard_position = (5, 5)
    hazard_tile = grid.get_tile(*hazard_position)
    assert hazard_tile is not None
    hazard = BaseCondition(
        name="Spike Field",
        source_entity_uuid=uuid4(),
        target_entity_uuid=hazard_tile.uuid,
        hazard_filter=HazardFilter.ALL,
    )
    hazard_tile.add_condition(hazard)

    scout = create_skeleton(name="Scout", position=(5, 3), faction="heroes")
    Entity.update_all_entities_senses()

    available = get_available_actions(scout)
    move_info = find_action(available, "Move")
    hazard_target = next(
        target for target in move_info.valid_targets if target.position == (5, 6)
    )

    assert hazard_target.is_path_hazardous is True
    assert hazard_target.path is not None
    assert hazard_target.safe_path is not None
    assert hazard_target.safe_path_cost is not None
    assert hazard_position in hazard_target.path[1:]
    assert hazard_position not in hazard_target.safe_path[1:]
    assert hazard_target.safe_path in (
        [(5, 3), (5, 4), (4, 5), (5, 6)],
        [(5, 3), (5, 4), (6, 5), (5, 6)],
    )

    movement_before = scout.action_economy.movement.normalized_score
    result = execute_by_index(
        scout,
        "Move",
        hazard_target.index,
        available=available,
        prefer_safe=True,
    )

    assert result is not None
    assert not result.canceled
    movement_result = cast(MovementEvent, result)
    assert movement_result.path == hazard_target.safe_path
    assert scout.position == hazard_target.position
    assert scout.action_economy.movement.normalized_score == (
        movement_before - hazard_target.safe_path_cost
    )

    safe_lines = [
        f"hazard target position: {hazard_target.position}",
        f"unsafe path: {hazard_target.path}",
        f"safe path: {hazard_target.safe_path}",
        f"hazardous path: {hazard_target.is_path_hazardous}",
        f"hazard in unsafe path: {hazard_position in hazard_target.path[1:]}",
        f"hazard in safe path: {hazard_position in hazard_target.safe_path[1:]}",
        f"safe path cost: {hazard_target.safe_path_cost}",
        f"executed path is safe path: {movement_result.path == hazard_target.safe_path}",
        f"movement after safe move: {scout.action_economy.movement.normalized_score}",
    ]

    print("\n".join(safe_lines))

    expected_safe_lines = [
        "hazard target position: (5, 6)",
        "unsafe path: [(5, 3), (5, 4), (5, 5), (5, 6)]",
        f"safe path: {hazard_target.safe_path}",
        "hazardous path: True",
        "hazard in unsafe path: True",
        "hazard in safe path: False",
        "safe path cost: 15",
        "executed path is safe path: True",
        "movement after safe move: 15",
    ]
    assert safe_lines == expected_safe_lines
    assert capsys.readouterr().out.splitlines() == expected_safe_lines


def test_move_executes_affordable_disclosed_path_when_safe_alternative_is_too_costly() -> None:
    """Execution must not replace a legal epoch path with an unaffordable route."""
    reset_action_state()
    scout = create_skeleton(name="Scout", position=(5, 3), faction="heroes")
    Entity.update_all_entities_senses()

    available = get_available_actions(scout)
    move_info = find_action(available, "Move")
    target = next(
        candidate for candidate in move_info.valid_targets
        if candidate.position == (5, 6)
    )
    assert target.position is not None
    assert target.path is not None
    assert target.path_cost is not None
    assert target.path_cost <= scout.action_economy.movement.normalized_score

    unaffordable_safe_path = [
        (5, 3),
        (4, 3),
        (3, 3),
        (2, 4),
        (2, 5),
        (3, 6),
        (4, 6),
        (5, 6),
    ]
    target.is_path_hazardous = True
    target.safe_path = unaffordable_safe_path
    target.safe_path_cost = 35
    scout.senses.safe_paths[target.position] = unaffordable_safe_path

    result = execute_by_index(
        scout,
        "Move",
        target.index,
        available=available,
        prefer_safe=True,
    )

    assert result is not None
    assert not result.canceled
    movement_result = cast(MovementEvent, result)
    assert movement_result.path == target.path
    assert scout.position == target.position


def test_partial_move_completion_reports_only_traversed_path_and_cost() -> None:
    """A newly discovered collision cannot survive as an untraversed log tail."""
    reset_action_state()
    scout = create_tutorial_actor(name="Scout", position=(0, 5))
    Entity.update_all_entities_senses()

    available = get_available_actions(scout)
    move_info = find_action(available, "Move")
    target = next(
        candidate for candidate in move_info.valid_targets
        if candidate.position == (6, 9)
    )
    disclosed_path = [
        (0, 5),
        (1, 5),
        (2, 5),
        (3, 6),
        (4, 7),
        (5, 8),
        (6, 9),
    ]
    target.path = disclosed_path
    target.path_cost = 30

    create_tutorial_actor(
        name="Unknown Blocker",
        position=(4, 7),
        faction="monsters",
        standard_actions=False,
    )

    result = execute_by_index(
        scout,
        "Move",
        target.index,
        available=available,
        prefer_safe=False,
    )

    assert result is not None
    assert not result.canceled
    movement_result = cast(MovementEvent, result)
    traversed_path = disclosed_path[:4]
    movement_cost = next(
        cost.cost for cost in movement_result.costs
        if cost.cost_type == "movement"
    )

    assert scout.position == (3, 6)
    assert scout.action_economy.movement.normalized_score == 15
    assert movement_result.end_position == (3, 6)
    assert movement_result.path == traversed_path
    assert movement_result.get_affected_positions() == set(traversed_path)
    assert (4, 7) not in movement_result.get_affected_positions()
    assert movement_cost == 15
    assert movement_result.combat_log is not None
    assert movement_result.combat_log.data["path"] == traversed_path
    assert movement_result.combat_log.data["distance_feet"] == 15
    assert movement_result.combat_log.data["movement_cost"] == 15
    assert len(movement_result.combat_log.sub_entries) == 3
    assert "15ft" in movement_result.combat_log.compact
