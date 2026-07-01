"""Tutorial tests for action templates, discovery, target indices, and costs."""

from typing import cast
from uuid import uuid4

from dnd.actions import Dash, MovementEvent
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
from dnd.core.base_actions import ActionCategory, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, HazardFilter
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items import create_healing_potion
from dnd.monsters.bestiary import create_goblin, create_skeleton


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


def test_first_action_example_prints_visible_turn_menu(capsys) -> None:
    """One actor prints grouped choices, target previews, and paid Dash state."""
    reset_action_state()
    hero = create_goblin(name="Scout", position=(5, 5), faction="heroes")
    create_skeleton(name="Skeleton", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses()

    available = get_available_actions(hero)
    dash_info = next(
        info for info in available.self_actions if info.template_name == "Dash"
    )
    move_info = next(
        info for info in available.position_actions if info.template_name == "Move"
    )
    attack_info = next(info for info in available.entity_actions if info.is_attack)
    move_target = move_info.valid_targets[0]
    attack_target = attack_info.valid_targets[0]
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
        "groups: entity=2, position=2, self=4, object=0",
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

    assert available.entity_uuid == hero.uuid
    assert available.remaining_movement == hero.action_economy.movement.normalized_score
    assert {"Dash", "Dodge", "Disengage"}.issubset(self_names)
    assert "Move" in position_names
    assert "Jump" in position_names

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
        Entity.get(target.target_uuid).name for target in attack_info.valid_targets
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
        "groups: entity=2, position=2, self=4, object=0",
        "self actions include: ['Dash', 'Disengage', 'Dodge']",
        "dash row: target=self, index=0, cost=1 actions, afford=True",
        "move row: category=movement, target=(5, 6), path=[(5, 5), (5, 6)]",
        "attack row: weapon=Scimitar, targets=['Skeleton']",
        "all actions ordered: True",
    ]
    assert discovery_lines == expected_discovery_lines
    assert capsys.readouterr().out.splitlines() == expected_discovery_lines


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


def test_floor_and_inventory_item_actions_are_discovered_and_routed(capsys) -> None:
    """Object and item-use actions appear through the same discovery result."""
    reset_action_state()
    actor = create_tutorial_actor(position=(3, 3))
    potion = create_healing_potion(uuid4())
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

    drink_result = execute_by_index(
        actor,
        drink_info.template_name,
        0,
        available=available,
    )

    assert drink_result is not None
    assert not drink_result.canceled
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
        Entity.get(target.target_uuid).name for target in default_attack.valid_targets
    ]

    ally_attack = find_attack_action(hero.get_available_actions(target_filter="allies"))
    assert [target.target_uuid for target in ally_attack.valid_targets] == [ally.uuid]
    ally_names = [
        Entity.get(target.target_uuid).name for target in ally_attack.valid_targets
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
        Entity.get(target.target_uuid).name for target in all_targets_attack.valid_targets
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
        "safe path: [(5, 3), (5, 4), (4, 5), (5, 6)]",
        "hazardous path: True",
        "hazard in unsafe path: True",
        "hazard in safe path: False",
        "safe path cost: 15",
        "executed path is safe path: True",
        "movement after safe move: 15",
    ]
    assert safe_lines == expected_safe_lines
    assert capsys.readouterr().out.splitlines() == expected_safe_lines
